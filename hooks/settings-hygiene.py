#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from typing import Iterable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib.audit_log import record as _audit  # noqa: E402


SETTINGS_FILENAMES = ("settings.json", "settings.local.json")
BLOCKLIST_PATH = os.path.expanduser("~/.claude/.settings-hygiene-blocklist")


def _masked(value: str) -> str:
    return INLINE_CREDENTIAL_RE.sub(
        lambda m: m.group(0).replace(f":{m.group('password')}@", ":****@"), value
    )


INLINE_CREDENTIAL_RE = re.compile(
    r"\b[a-zA-Z][a-zA-Z0-9+.-]*://"
    r"(?P<user>[^:/@\s${}]+):"
    r"(?P<password>[^@/\s${}]+)@"
)

HOME_PATH_RE = re.compile(
    r"(?:^|[\s\"'=:])(?:/Users/[^/\s\"']+|/home/[^/\s\"']+|[A-Za-z]:\\Users\\[^\\\s\"']+)/"
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


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
    if "edits" in tool_input:
        return "\n".join(edit.get("new_string", "") for edit in tool_input["edits"])
    return None


def _is_settings_target(path: str) -> bool:
    base = os.path.basename(path)
    return base in SETTINGS_FILENAMES


def _check_string(s: str, blocklist: list[str]) -> str | None:
    cred_match = INLINE_CREDENTIAL_RE.search(s)
    if cred_match:
        password = cred_match.group("password")
        if not password.startswith("${") and password not in {
            "",
            "<password>",
            "REPLACE_ME",
        }:
            return (
                "inline credential in connection string. "
                "The password literal should be `${ENV_VAR}`."
            )
    if HOME_PATH_RE.search(s):
        return "absolute home path leaks the user's machine layout. Use `~`, `${HOME}`, or `${VAR}`."
    for token in blocklist:
        if token and token in s:
            return f"blocklisted identifier `{token}`. See ~/.claude/.settings-hygiene-blocklist."
    return None


from _lib.settings_hygiene_structure import check_structure  # noqa: E402
from _lib.hook_profile import should_run  # noqa: E402


PORTABILITY_GUIDANCE = (
    "\nKeep ~/.claude/settings.json portable across machines and projects.\n"
    "Use `${ENV_VAR}` placeholders, `~` for home, and add per-project tokens to\n"
    "~/.claude/.settings-hygiene-blocklist if you want them flagged on future edits.\n"
    "Bypass once: set SETTINGS_HYGIENE_DISABLE=1 in the environment."
)


def _exit_when_disabled() -> None:
    if not should_run("settings-hygiene"):
        sys.exit(0)
    if os.environ.get("SETTINGS_HYGIENE_DISABLE") == "1":
        sys.exit(0)
    if is_bypassed("settings-hygiene"):
        sys.exit(0)


def _scan_target(proposed: str) -> object:
    try:
        return json.loads(proposed)
    except json.JSONDecodeError:
        return proposed


def _string_findings(scan_target: object) -> list[tuple[str, str]]:
    blocklist = _load_blocklist()
    checked = ((s, _check_string(s, blocklist)) for s in _walk_strings(scan_target))
    return [(s[:120], reason) for s, reason in checked if reason]


def _print_string_findings(findings: list[tuple[str, str]]) -> None:
    if not findings:
        return
    print(
        "BLOCKED: settings.json contains project- or machine-specific data.\n",
        file=sys.stderr,
    )
    for value, reason in findings[:10]:
        print(f"  - {reason}\n    value: {_masked(value)}", file=sys.stderr)


def _print_structure_findings(
    structure_findings: list[str], after_strings: bool
) -> None:
    if not structure_findings:
        return
    if after_strings:
        print("", file=sys.stderr)
    print(
        "BLOCKED: settings.json has structural problems.\n",
        file=sys.stderr,
    )
    for reason in structure_findings[:10]:
        print(f"  - {reason}", file=sys.stderr)


def _first_reason(
    findings: list[tuple[str, str]], structure_findings: list[str]
) -> str:
    return findings[0][1] if findings else structure_findings[0]


def _settings_path(tool_input: dict) -> str:
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not file_path or not _is_settings_target(file_path):
        sys.exit(0)
    return file_path


def main() -> None:
    _exit_when_disabled()
    data = read_hook_payload("settings-hygiene")

    tool_input = data.get("tool_input", data.get("input", {}))
    file_path = _settings_path(tool_input)

    proposed = _proposed_content(tool_input)
    if not proposed:
        sys.exit(0)

    scan_target = _scan_target(proposed)
    findings = _string_findings(scan_target)
    structure_findings = check_structure(scan_target)

    if not findings and not structure_findings:
        sys.exit(0)

    _print_string_findings(findings)
    _print_structure_findings(structure_findings, bool(findings))
    print(PORTABILITY_GUIDANCE, file=sys.stderr)
    _audit(
        hook="settings-hygiene",
        decision="block",
        tool=data.get("tool_name", "Write"),
        reason=_first_reason(findings, structure_findings),
        file_path=file_path,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
