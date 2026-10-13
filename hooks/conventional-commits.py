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
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.git_invocation import strip_git_global_options  # noqa: E402
from _lib.shell_segments import strip_heredoc_bodies  # noqa: E402

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
CAT_HEREDOC_RE = re.compile(
    r"cat <<\s*'?(\w+)'?\s*\n(.+?)\n\s*\1\s*$", re.DOTALL | re.MULTILINE
)
ANY_HEREDOC_RE = re.compile(
    r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(.*?)\n\s*\1\s*$", re.DOTALL | re.MULTILINE
)
SHORT_CLUSTER_RE = re.compile(r"-[a-zA-Z]+")


def _read_payload() -> tuple[str, str]:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    tool_input = data.get("tool_input") or data.get("input") or {}
    if not isinstance(tool_input, dict):
        return "", ""
    value = tool_input.get("command", "")
    cwd = data.get("cwd", "")
    return (
        value if isinstance(value, str) else "",
        cwd if isinstance(cwd, str) else "",
    )


def _commit_tokens(command: str) -> list[str]:
    try:
        tokens = shlex.split(strip_heredoc_bodies(command), posix=True)
    except ValueError:
        return []
    for index in range(len(tokens) - 1):
        if tokens[index] == "git" and "commit" in tokens[index + 1 : index + 8]:
            start = tokens.index("commit", index + 1) + 1
            return tokens[start:]
    return []


def _option_value(token: str, following: str | None) -> tuple[str, str | None]:
    if token in ("-m", "--message"):
        return "message", following
    if token in ("-F", "--file"):
        return "file", following
    if token.startswith("--message="):
        return "message", token.split("=", 1)[1]
    if token.startswith("--file="):
        return "file", token.split("=", 1)[1]
    if SHORT_CLUSTER_RE.fullmatch(token) is None and token.startswith("-m"):
        return "message", token[2:]
    if SHORT_CLUSTER_RE.fullmatch(token) and token[-1] in "mF":
        return ("message" if token[-1] == "m" else "file"), following
    return "", None


def _message_sources(tokens: list[str]) -> tuple[list[str], list[str]]:
    messages: list[str] = []
    files: list[str] = []
    for index, token in enumerate(tokens):
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        kind, value = _option_value(token, following)
        if value is None:
            continue
        if kind == "message":
            messages = [*messages, value]
        elif kind == "file":
            files = [*files, value]
    return messages, files


def _read_message_file(path: str, command: str, cwd: str) -> str:
    if path == "-":
        heredoc = ANY_HEREDOC_RE.search(command)
        return heredoc.group(2) if heredoc else ""
    resolved = Path(os.path.expanduser(path))
    if cwd and not resolved.is_absolute():
        resolved = Path(cwd) / resolved
    try:
        return resolved.read_text(encoding="utf-8")
    except OSError as error:
        sys.stderr.write(f"{HOOK_NAME}: cannot read {resolved}: {error}\n")
        return ""


def _extract_message(command: str, cwd: str = "") -> str:
    heredoc = CAT_HEREDOC_RE.search(command)
    if heredoc:
        return heredoc.group(2).strip()
    messages, files = _message_sources(_commit_tokens(command))
    if files:
        return _read_message_file(files[0], command, cwd).strip()
    return "\n\n".join(message.strip() for message in messages).strip()


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


def _shortening_hint(subject: str) -> str:
    """Return a ready-to-use shorter subject when dropping the scope fits."""
    match = SUBJECT_RE.match(subject)
    if match is None or not match.group(2):
        return ""
    unscoped = subject.replace(match.group(2), "", 1)
    if len(unscoped) > 50:
        return ""
    return f"  Dropping the scope fits: {unscoped}\n"


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
            f"  Got:    {subject}\n"
            f"  Cut at: {subject[:50]}|{subject[50:]}\n\n"
            f"  Drop {len(subject) - 50} character(s) before the `|`.\n"
            + _shortening_hint(subject)
            + "  Move the detail you cut into the commit body.\n"
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
    command, cwd = _read_payload()
    if not COMMIT_RE.search(strip_git_global_options(command)):
        return 0
    if SKIP_RE.search(command):
        return 0
    message = _extract_message(command, cwd)
    if not message:
        return 0
    return _validate(message, command)


if __name__ == "__main__":
    raise SystemExit(main())
