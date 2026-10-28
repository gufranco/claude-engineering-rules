#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.audit_log import record as _audit  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.shell_segments import strip_heredoc_bodies  # noqa: E402

HOOK_ID = "zsh-special-name-guard"
BYPASS_ENV = "ZSH_SPECIAL_NAME_GUARD_DISABLE"
SPECIAL_NAMES = (
    "path",
    "status",
    "argv",
    "cdpath",
    "fpath",
    "manpath",
    "mailpath",
    "module_path",
    "fignore",
    "psvar",
    "watch",
)
NAMES = "|".join(SPECIAL_NAMES)
BOUNDARY = r"(?:^|(?<=[\s;&|(){}]))"
DECLARATION = rf"{BOUNDARY}(?:local|typeset|declare|export|readonly|integer|float)(?:\s+-\w+)*\s+(?:{NAMES})\b"
COMMAND_START = r"(?:^|(?<=[;&|(){}]))\s*(?:(?:then|do|else|elif|!)\s+)?(?:\w+=\S*\s+)*"
ASSIGNMENT = rf"{COMMAND_START}(?:{NAMES})(?:\[[^\]]*\])?\+?="
LOOP_VARIABLE = rf"{BOUNDARY}(?:for|select)\s+(?:{NAMES})\s+in\b"
READ_TARGET = rf"{BOUNDARY}read\b[^;&|\n]*\s(?:{NAMES})(?=$|[\s;&|])"
SPECIAL_NAME_USE = re.compile(
    "|".join((DECLARATION, ASSIGNMENT, LOOP_VARIABLE, READ_TARGET)), re.MULTILINE
)
LEADING_EQUALS = re.compile(r"(?:^|(?<=[\s;&|(]))=\S+", re.MULTILINE)
DOUBLE_BRACKET = re.compile(r"\[\[.*?\]\]", re.DOTALL)
ARITHMETIC = re.compile(r"\(\(.*?\)\)", re.DOTALL)

SPECIAL_NAME_REASON = (
    "BLOCKED: a zsh special name used as a variable. In zsh, `path`, `status`, "
    "`argv`, `cdpath`, `fpath`, `manpath`, `mailpath`, `module_path`, `fignore`, "
    "`psvar`, and `watch` are tied to shell state: assigning `path` replaces PATH, "
    "so every later command reports `command not found`.\n"
    "Fix: rename the variable, such as `target`, `file`, `dir`, or `rc`.\n"
    f"Bypass (one-off): set {BYPASS_ENV}=1 in the parent shell."
)
LEADING_EQUALS_REASON = (
    "BLOCKED: an unquoted word with a leading equals sign. zsh expands `=word` to "
    "the path of the command named `word`, so `echo ==up` fails with "
    "`=up not found` and every later line of the command is skipped.\n"
    "Fix: quote the word, `echo '== up'`, or use `[[ a == b ]]` instead of `[ a == b ]`.\n"
    f"Bypass (one-off): set {BYPASS_ENV}=1 in the parent shell."
)
UNREADABLE_REASON = (
    "BLOCKED: zsh-special-name-guard could not read its input: stdin is not UTF-8 JSON."
)


def mask_quoted(text: str) -> str:
    out: list[str] = []
    quote = ""
    escaped = False
    for char in text:
        if escaped:
            out = [*out, " " if quote else char]
            escaped = False
            continue
        if char == "\\" and quote != "'":
            escaped = True
            out = [*out, " " if quote else char]
            continue
        if quote:
            closing = char == quote
            out = [*out, char if closing else ("\n" if char == "\n" else " ")]
            quote = "" if closing else quote
            continue
        if char in "'\"":
            quote = char
        out = [*out, char]
    return "".join(out)


def blank(pattern: re.Pattern[str], text: str) -> str:
    return pattern.sub(lambda match: " " * len(match.group(0)), text)


def executable_text(command: str) -> str:
    masked = mask_quoted(strip_heredoc_bodies(command))
    return blank(ARITHMETIC, blank(DOUBLE_BRACKET, masked))


def violation(command: str) -> str:
    text = executable_text(command)
    if SPECIAL_NAME_USE.search(text):
        return SPECIAL_NAME_REASON
    if LEADING_EQUALS.search(text):
        return LEADING_EQUALS_REASON
    return ""


def runs_under_zsh() -> bool:
    return os.path.basename(os.environ.get("SHELL", "")) == "zsh"


def block(reason: str, command: str) -> int:
    sys.stderr.write(reason + "\n")
    _audit(
        hook=HOOK_ID,
        decision="block",
        tool="Bash",
        reason=reason.splitlines()[0][:200],
        command_excerpt=command[:240],
    )
    return 2


def read_payload() -> "dict[str, object] | None":
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def main() -> int:
    if os.environ.get(BYPASS_ENV) == "1" or is_bypassed(HOOK_ID):
        return 0
    if not runs_under_zsh():
        return 0
    data = read_payload()
    if data is None:
        return block(UNREADABLE_REASON, "")
    if data.get("tool_name") != "Bash":
        return 0
    tool_input = data.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    reason = violation(command) if isinstance(command, str) else ""
    if not reason:
        return 0
    return block(reason, command)


if __name__ == "__main__":
    sys.exit(main())
