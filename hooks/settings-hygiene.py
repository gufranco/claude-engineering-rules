#!/usr/bin/env python3
"""Keep ~/.claude/settings.json project-agnostic.

Runs on PreToolUse for Write/Edit/MultiEdit when the target file is named
`settings.json`. Parses the proposed content as JSON and walks every string
value, rejecting payloads that leak machine- or project-specific data:

  1. Inline credentials in URLs, e.g. `postgresql://user:password@host/db`
     where the password is a literal, not `${VAR}` or empty.
  2. Absolute home paths (`/Users/<name>/...`, `/home/<name>/...`,
     `C:\\Users\\<name>\\...`). These tie the global config to one machine.
  3. Identifiers from a user-maintained blocklist at
     `~/.claude/.settings-hygiene-blocklist`. One entry per line. Comments
     start with `#`. Useful for project names, internal hostnames, database
     names, and anything else the user wants to keep out of the global
     config but the regex above does not catch.

Exit 0 = allow, exit 2 = block.

Bypass:
  - Set `SETTINGS_HYGIENE_DISABLE=1` in the environment for one-off overrides.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Iterable

sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
try:
    from audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover
    def _audit(**_fields):  # type: ignore
        return None


SETTINGS_FILENAMES = ("settings.json", "settings.local.json")
BLOCKLIST_PATH = os.path.expanduser("~/.claude/.settings-hygiene-blocklist")

INLINE_CREDENTIAL_RE = re.compile(
    r"\b[a-zA-Z][a-zA-Z0-9+.-]*://"
    r"(?P<user>[^:/@\s${}]+):"
    r"(?P<password>[^@/\s${}]+)@"
)

HOME_PATH_RE = re.compile(
    r"(?:^|[\s\"'=:])(?:/Users/[^/\s\"']+|/home/[^/\s\"']+|[A-Za-z]:\\Users\\[^\\\s\"']+)/"
)


def _load_blocklist() -> list[str]:
    if not os.path.exists(BLOCKLIST_PATH):
        return []
    try:
        with open(BLOCKLIST_PATH, encoding="utf-8") as f:
            return [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith("#")
            ]
    except OSError:
        return []


def _walk_strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _walk_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk_strings(v)


def _proposed_content(tool_input: dict) -> str | None:
    if "content" in tool_input:
        return tool_input.get("content")
    if "new_string" in tool_input:
        return tool_input.get("new_string")
    if "edits" in tool_input and isinstance(tool_input["edits"], list):
        return "\n".join(
            edit.get("new_string", "")
            for edit in tool_input["edits"]
            if isinstance(edit, dict)
        )
    return None


def _is_settings_target(path: str) -> bool:
    base = os.path.basename(path)
    return base in SETTINGS_FILENAMES


def _check_string(s: str, blocklist: list[str]) -> str | None:
    cred_match = INLINE_CREDENTIAL_RE.search(s)
    if cred_match:
        password = cred_match.group("password")
        if not password.startswith("${") and password not in {"", "<password>", "REPLACE_ME"}:
            return (
                "inline credential in connection string. "
                f"Password literal `{password[:4]}...` should be `${{ENV_VAR}}`."
            )
    if HOME_PATH_RE.search(s):
        return "absolute home path leaks the user's machine layout. Use `~`, `${HOME}`, or `${VAR}`."
    for token in blocklist:
        if token and token in s:
            return f"blocklisted identifier `{token}`. See ~/.claude/.settings-hygiene-blocklist."
    return None


def main() -> None:
    if os.environ.get("SETTINGS_HYGIENE_DISABLE") == "1":
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = data.get("tool_input", data.get("input", {}))
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not file_path or not _is_settings_target(file_path):
        sys.exit(0)

    proposed = _proposed_content(tool_input)
    if not proposed:
        sys.exit(0)

    try:
        parsed = json.loads(proposed)
    except json.JSONDecodeError:
        scan_target: object = proposed
    else:
        scan_target = parsed

    blocklist = _load_blocklist()
    findings: list[tuple[str, str]] = []
    for s in _walk_strings(scan_target):
        reason = _check_string(s, blocklist)
        if reason:
            findings.append((s[:120], reason))

    if not findings:
        sys.exit(0)

    print("BLOCKED: settings.json contains project- or machine-specific data.\n")
    for value, reason in findings[:10]:
        print(f"  - {reason}\n    value: {value}")
    print(
        "\nKeep ~/.claude/settings.json portable across machines and projects.\n"
        "Use `${ENV_VAR}` placeholders, `~` for home, and add per-project tokens to\n"
        "~/.claude/.settings-hygiene-blocklist if you want them flagged on future edits.\n"
        "Bypass once: set SETTINGS_HYGIENE_DISABLE=1 in the environment."
    )
    _audit(
        hook="settings-hygiene",
        decision="block",
        tool=data.get("tool_name", "Write"),
        reason=findings[0][1],
        file_path=file_path,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
