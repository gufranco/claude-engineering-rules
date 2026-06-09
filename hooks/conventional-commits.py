#!/usr/bin/env python3
"""PreToolUse Bash hook: validate `git commit` message against conventional format.

Extracts the message from `-m '<text>'`, `-m "<text>"`, or heredoc-style
`-m $(cat <<'X' ... X )`. Skips amend/no-edit/squash. Validates:
    1. Subject matches `<type>(<scope>)?(!)?: <subject>`.
    2. Subject is at most 50 characters.
    3. Body lines are at most 72 characters (trailers, URLs, indented code skipped).
    4. `Rejected:` trailers include a `|` separator before the reason.

Bypass channels:
    1. Env var `CONVENTIONAL_COMMITS_DISABLE=1` (parent shell).
    2. File registry entry for hook `conventional-commits`.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.bypass import is_bypassed  # noqa: E402

try:
    from _lib.audit_log import record as _audit_record
except Exception:  # noqa: BLE001
    _audit_record = None  # type: ignore[assignment]

HOOK_NAME = "conventional-commits"
ENV_DISABLE = "CONVENTIONAL_COMMITS_DISABLE"
COMMIT_RE = re.compile(r"\bgit\s+commit\b")
SKIP_RE = re.compile(r"--amend|--no-edit|--squash")
SUBJECT_RE = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert)(\([^)]+\))?(!)?: .+"
)
TRAILER_PREFIX_RE = re.compile(r"^(Rejected|Constraint|Risk):")
TRAILER_VALID_RE = re.compile(r"^(Rejected|Constraint|Risk): .+")
REJECTED_PIPE_RE = re.compile(r"^Rejected: .+ \| .+")
SKIP_BODY_LINE_RE = re.compile(
    r"^(Rejected|Constraint|Risk|Fixes|Closes|Refs|Co-authored-by|Signed-off-by|BREAKING CHANGE):"
)
INDENTED_OR_URL_RE = re.compile(r"^(    |\t|https?://)")
QUOTED_M_RE = re.compile(r"-m\s+['\"](.+?)['\"]", re.DOTALL)
HEREDOC_RE = re.compile(
    r"cat <<\s*'?(\w+)'?\s*\n(.+?)\n\s*\1\s*$", re.DOTALL | re.MULTILINE
)


def _read_command() -> str:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    tool_input = data.get("tool_input") or data.get("input") or {}
    if not isinstance(tool_input, dict):
        return ""
    value = tool_input.get("command", "")
    return value if isinstance(value, str) else ""


def _extract_message(command: str) -> str:
    heredoc = HEREDOC_RE.search(command)
    if heredoc:
        return heredoc.group(2).strip()
    quoted = QUOTED_M_RE.search(command)
    if quoted:
        return quoted.group(1).strip()
    return ""


def _audit(reason: str, command: str) -> None:
    if _audit_record is None:
        return
    try:
        _audit_record(
            hook=HOOK_NAME,
            decision="block",
            decision_class="block",
            reason=reason,
            tool="Bash",
            command_excerpt=command[:200],
        )
    except Exception:  # noqa: BLE001
        pass


def _block(message: str, reason: str, command: str) -> int:
    sys.stderr.write(message)
    if not message.endswith("\n"):
        sys.stderr.write("\n")
    _audit(reason, command)
    return 2


def _validate(message: str, command: str) -> int:
    lines = message.splitlines()
    if not lines:
        return 0
    subject = lines[0]
    if not SUBJECT_RE.match(subject):
        body = (
            "BLOCKED: Commit message does not follow conventional commit format.\n\n"
            f"  Got: {subject}\n\n"
            "  Expected: <type>(<scope>): <subject>\n"
            "  Types: feat, fix, docs, style, refactor, perf, test, chore, ci, build, revert\n"
            "  Example: feat(auth): add SSO login with Google provider\n"
        )
        return _block(body, "subject not conventional format", command)
    if len(subject) > 50:
        body = (
            f"BLOCKED: Commit subject line is {len(subject)} characters (max 50).\n\n"
            f"  Got: {subject}\n\n"
            "  Keep the subject concise. Use the body for details.\n"
        )
        return _block(body, "subject too long", command)
    for idx, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        if SKIP_BODY_LINE_RE.match(line):
            continue
        if INDENTED_OR_URL_RE.match(line):
            continue
        if len(line) > 72:
            body = (
                f"BLOCKED: Commit body line {idx} is {len(line)} characters (max 72).\n\n"
                f"  Got: {line}\n\n"
                "  Wrap body lines at 72 characters.\n"
            )
            return _block(body, "body line too long", command)
    for line in lines:
        if not TRAILER_PREFIX_RE.match(line):
            continue
        if not TRAILER_VALID_RE.match(line):
            body = (
                "BLOCKED: Malformed decision trailer.\n\n"
                f"  Got: {line}\n\n"
                "  Expected: <Trailer>: <description>\n"
            )
            return _block(body, "malformed decision trailer", command)
        if line.startswith("Rejected:") and not REJECTED_PIPE_RE.match(line):
            body = (
                "BLOCKED: Rejected trailer must include reason after pipe.\n\n"
                f"  Got: {line}\n\n"
                "  Expected: Rejected: <alternative> | <reason>\n"
            )
            return _block(body, "Rejected trailer missing pipe", command)
    return 0


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1":
        return 0
    if is_bypassed(HOOK_NAME):
        return 0
    command = _read_command()
    if not COMMIT_RE.search(command):
        return 0
    if SKIP_RE.search(command):
        return 0
    message = _extract_message(command)
    if not message:
        return 0
    return _validate(message, command)


if __name__ == "__main__":
    raise SystemExit(main())
