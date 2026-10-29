#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from itertools import takewhile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.audit_log import record as _audit  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402

HOOK_NAME = "user-commands-one-line"
DISABLE_ENV = "USER_COMMANDS_ONE_LINE_DISABLE"
TAIL_BYTES = 512 * 1024
MAX_COMMANDS = 1
BANG_LINE = re.compile(r"^\s*!\s+\S")
STRICT_MODE = re.compile(r"\bset\s+-[a-z]*e")
SILENCERS = frozenset({"true", ":"})
SEPARATORS = frozenset({"&&", "||", ";", "|", "&", "(", ")"})
REASON = (
    "This reply breaks the one-line rule for commands the user runs: {problems}. "
    "Hand one safe line: `! (set -euo pipefail && S=/abs/path && <check that exits "
    'non-zero on a bad state> && <change> && rm -rf "${{S:?}}/tmp")`. A check whose '
    "output the user must read before a risky step is not chained: run it first, "
    "or hand it alone and the change in the next turn. Full rule: "
    "~/.claude/standards/user-commands-one-line.md."
)


def _tail_lines(path: Path) -> list[str]:
    with path.open("rb") as handle:
        size = handle.seek(0, os.SEEK_END)
        handle.seek(max(0, size - TAIL_BYTES))
        lines = handle.read().decode("utf-8", errors="replace").splitlines()
    return lines[1:] if size > TAIL_BYTES else lines


def _blocks(entry: dict[str, object]) -> list[object]:
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return content if isinstance(content, list) else []


def _texts(entry: dict[str, object]) -> list[str]:
    return [
        str(block.get("text", ""))
        for block in _blocks(entry)
        if isinstance(block, dict) and block.get("type") == "text"
    ]


def _is_prompt(entry: dict[str, object]) -> bool:
    kinds = {block.get("type") for block in _blocks(entry) if isinstance(block, dict)}
    return (
        entry.get("type") == "user" and "tool_result" not in kinds and "text" in kinds
    )


def _parse(line: str) -> dict[str, object] | None:
    try:
        entry = json.loads(line)
    except ValueError:
        return None
    return entry if isinstance(entry, dict) else None


def final_reply(lines: list[str]) -> str:
    reply: tuple[str, ...] = ()
    for entry in filter(None, map(_parse, lines)):
        if _is_prompt(entry):
            reply = ()
        elif entry.get("type") == "assistant":
            reply = (*reply, *_texts(entry))
    return "\n".join(reply)


def command_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if BANG_LINE.match(line)]


def _tokens(line: str) -> list[str]:
    body = line.strip()[1:]
    try:
        return list(shlex.shlex(body, posix=True, punctuation_chars=True))
    except ValueError:
        return []


def _rm_calls(tokens: list[str]) -> list[list[str]]:
    return [
        list(takewhile(lambda arg: arg not in SEPARATORS, tokens[index + 1 :]))
        for index, token in enumerate(tokens)
        if token == "rm"
    ]


def _recursive_rm_args(tokens: list[str]) -> list[str]:
    return [
        arg
        for args in _rm_calls(tokens)
        if any(a.startswith("-") and "r" in a.lower() for a in args)
        for arg in args
        if not arg.startswith("-")
    ]


def line_problems(line: str) -> list[str]:
    tokens = _tokens(line)
    pairs = zip(tokens, tokens[1:], strict=False)
    checks = (
        (
            ";" in tokens and not STRICT_MODE.search(line),
            "steps joined with `;`, which runs the next step after a failure",
        ),
        (
            any(a == "||" and b in SILENCERS for a, b in pairs),
            "a failure silenced with `|| true`",
        ),
        (
            any("$" in a and ":?" not in a for a in _recursive_rm_args(tokens)),
            "a recursive delete of a path built from a variable without `${VAR:?}`",
        ),
    )
    return [text for hit, text in checks if hit]


def problems(text: str) -> list[str]:
    lines = command_lines(text)
    found = [f"{len(lines)} separate commands"] if len(lines) > MAX_COMMANDS else []
    return found + [problem for line in lines for problem in line_problems(line)]


def _reply_text(data: dict[str, object]) -> str:
    direct = data.get("last_assistant_message")
    if isinstance(direct, str) and direct:
        return direct
    transcript = data.get("transcript_path")
    if not isinstance(transcript, str) or not transcript:
        return ""
    try:
        return final_reply(_tail_lines(Path(transcript)))
    except OSError as exc:
        sys.stderr.write(f"{HOOK_NAME}: transcript not read: {exc}\n")
        return ""


def handle_stop(data: dict[str, object]) -> int:
    if data.get("stop_hook_active") is True:
        return 0
    found = problems(_reply_text(data))
    if not found:
        return 0
    summary = "; ".join(found)
    sys.stdout.write(
        json.dumps({"decision": "block", "reason": REASON.format(problems=summary)})
    )
    _audit(
        hook=HOOK_NAME,
        decision="block",
        decision_class="block",
        reason=summary[:200],
    )
    return 0


def main() -> int:
    if os.environ.get(DISABLE_ENV) == "1" or is_bypassed(HOOK_NAME):
        return 0
    return handle_stop(read_hook_payload(HOOK_NAME))


if __name__ == "__main__":
    sys.exit(main())
