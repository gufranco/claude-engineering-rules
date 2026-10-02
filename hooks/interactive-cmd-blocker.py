#!/usr/bin/env python3
"""Block commands that hang the agent: interactive cp/mv/rm and macOS kcov.

On macOS, the default shell often aliases `rm` to `rm -i`, `cp` to `cp -i`,
and `mv` to `mv -i`. When an agent runs one of these against an existing
path, the shell prompts for confirmation, the agent has no stdin, and the
command hangs until the harness timeout.

The fix: require an explicit `-f` flag on cp/mv/rm. The user can still bypass
for the rare legitimate interactive use with INTERACTIVE_CMD_DISABLE=1.

On macOS, kcov 43 checks `/bin/bash`, which is bash 3.2, decides BASH_XTRACEFD
is unsupported, and streams every trace line through stderr. A 636-line bats
suite that takes 14 s alone grew past 1.5 GB in 180 s under it; larger suites
held 44 GB and ran 74 minutes. A native macOS kcov number is also wrong:
76.89% where Linux measures 98.74%. So on macOS, `kcov` and a `make coverage`
whose Makefile calls kcov are blocked with the Linux-container recipe instead.

Triggers PreToolUse on Bash. Exit 0 = allow, exit 2 = block.

Bypass: INTERACTIVE_CMD_DISABLE=1 in the parent shell.

Closes a gap left by dangerous-command-blocker.py.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


COMMAND_BOUNDARY = r"(?:^|[;&|]\s*|&&\s*|\|\|\s*)"

INTERACTIVE_PRONE = ("rm", "cp", "mv")
MAKE_COMMANDS = ("make", "gmake")
MAKEFILE_NAMES = ("GNUmakefile", "makefile", "Makefile")
COVERAGE_TARGET = "coverage"
MAKEFILE_READ_LIMIT = 1_000_000
OPERATOR_CHARS = ";&|"
HEREDOC_START = re.compile(r"(?<!<)<<(?!<)-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")
KCOV_REASON = (
    "BLOCKED: kcov on macOS. Homebrew kcov 43 traces bash through stderr here, "
    "which has held 44 GB and run 74 minutes, and its number is wrong: "
    "76.89% on macOS where Linux measures 98.74%.\n"
    "Fix: measure in Linux the way CI does. Pipe the committed tree into a "
    "container, `git archive HEAD | docker run --rm -i --memory=2g ubuntu:26.04 "
    "bash -c '...'`, install bats, tmux, make, python3 and the kcov build "
    "dependencies, build kcov from source, and run `make coverage` as a "
    "non-root user. Or push and read the CI coverage job.\n"
    "Bypass (one-off): set INTERACTIVE_CMD_DISABLE=1 in parent shell."
)

from _lib.bypass import is_bypassed  # noqa: E402


def split_commands(command: str) -> list[str]:
    """Split a bash command line by shell separators ; && || | &."""
    parts = re.split(r"\s*(?:;|&&|\|\||\||&)\s*", command)
    return [p.strip() for p in parts if p.strip()]


def has_force_flag(tokens: list[str]) -> bool:
    """Check if any token expresses --force or -f (including combined like -rf)."""
    for tok in tokens[1:]:
        if not tok.startswith("-"):
            continue
        if tok == "--force":
            return True
        if tok.startswith("--"):
            continue
        if "f" in tok[1:]:
            return True
    return False


def command_head(tokens: list[str]) -> tuple[str, list[str]]:
    """Return the base command name and its tokens, past env and `command`."""
    i = 0
    while i < len(tokens) and "=" in tokens[i] and not tokens[i].startswith("-"):
        i += 1
    if i >= len(tokens):
        return "", []
    if tokens[i] == "command" and i + 1 < len(tokens):
        i += 1
    return os.path.basename(tokens[i]), tokens[i:]


def tokenize(sub: str) -> list[str]:
    try:
        return shlex.split(sub)
    except ValueError:
        return []


def is_blocked(command: str) -> tuple[bool, str]:
    """Return (blocked, reason). Reason includes the command name."""
    for sub in split_commands(command):
        base, effective = command_head(tokenize(sub))
        if base not in INTERACTIVE_PRONE:
            continue
        if not has_force_flag(effective):
            return True, base
    return False, ""


def make_dir_and_files(args: list[str], cwd: str) -> tuple[str, list[str]]:
    """Resolve `-C dir` and `-f file` from make arguments."""
    directory = cwd
    files: list[str] = []
    for flag, value in zip(args, args[1:]):
        if flag == "-C":
            directory = os.path.join(directory, os.path.expanduser(value))
        elif flag == "-f":
            files = [*files, value]
    return directory, files or list(MAKEFILE_NAMES)


def makefile_uses_kcov(directory: str, names: list[str]) -> bool:
    for name in names:
        path = os.path.join(directory, name)
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                return "kcov" in handle.read(MAKEFILE_READ_LIMIT)
        except OSError:
            continue
    return False


def runs_kcov(base: str, args: list[str], cwd: str) -> bool:
    if base == "kcov":
        return True
    if base not in MAKE_COMMANDS or COVERAGE_TARGET not in args[1:]:
        return False
    directory, names = make_dir_and_files(args[1:], cwd)
    return makefile_uses_kcov(directory, names)


def strip_heredoc_bodies(command: str) -> str:
    """Drop the body lines of every heredoc, which are data, never commands."""
    kept: list[str] = []
    delimiter = ""
    for line in command.splitlines():
        if delimiter:
            if line.strip() == delimiter:
                delimiter = ""
            continue
        kept = [*kept, line]
        match = HEREDOC_START.search(line)
        if match:
            delimiter = match.group(1)
    return "\n".join(kept)


def line_segments(line: str) -> list[list[str]]:
    """Split one line into commands at unquoted ; & | operators."""
    lexer = shlex.shlex(line, posix=True, punctuation_chars=OPERATOR_CHARS)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return []
    segments: list[list[str]] = [[]]
    for token in tokens:
        if set(token) <= set(OPERATOR_CHARS):
            segments = [*segments, []]
        else:
            segments = [*segments[:-1], [*segments[-1], token]]
    return [segment for segment in segments if segment]


def quoted_segments(command: str) -> list[list[str]]:
    lines = strip_heredoc_bodies(command).splitlines()
    return [segment for line in lines for segment in line_segments(line)]


def kcov_blocked(command: str, cwd: str, platform: str) -> bool:
    """True when this command would start kcov natively on macOS."""
    if platform != "darwin":
        return False
    current = cwd
    for tokens in quoted_segments(command):
        base, args = command_head(tokens)
        if base == "cd" and len(args) > 1:
            current = os.path.join(current, os.path.expanduser(args[1]))
            continue
        if runs_kcov(base, args, current):
            return True
    return False


def emit_block(reason: str, command: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stderr.write(reason)
    _audit(
        hook="interactive-cmd-blocker",
        decision="block",
        decision_class="block",
        reason=reason[:200],
        tool="Bash",
        command_excerpt=command[:200],
    )
    sys.exit(2)


def main() -> int:
    if os.environ.get("INTERACTIVE_CMD_DISABLE") == "1":
        return 0
    if is_bypassed("interactive-cmd-blocker"):
        return 0

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if data.get("tool_name") != "Bash":
        return 0

    command = (data.get("tool_input") or {}).get("command", "")
    if not command:
        return 0

    cwd = data.get("cwd") or os.getcwd()
    if kcov_blocked(command, cwd, sys.platform):
        emit_block(KCOV_REASON, command)

    blocked, base = is_blocked(command)
    if not blocked:
        return 0

    reason = (
        f"BLOCKED: `{base}` invoked without `-f`. On macOS this often hangs "
        f"because the default alias adds `-i` and prompts for confirmation "
        f"that the agent cannot answer.\n"
        f"Fix: add `-f` (e.g. `{base} -f <path>` or `{base} -rf <path>` for "
        f"directories).\n"
        f"Bypass (one-off): set INTERACTIVE_CMD_DISABLE=1 in parent shell."
    )
    emit_block(reason, command)
    return 2


if __name__ == "__main__":
    sys.exit(main())
