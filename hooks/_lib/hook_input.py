from __future__ import annotations

import json
import sys
from typing import NoReturn

UNREADABLE_EXIT = 2
STRING_FIELDS = (
    "command",
    "file_path",
    "content",
    "new_string",
    "old_string",
    "prompt",
)


def refuse_unreadable(hook: str, reason: str) -> NoReturn:
    sys.stderr.write(
        f"Blocked: {hook} could not read its input: {reason}. A guard that "
        "cannot read its input fails closed. Retry the call; if this repeats, "
        "the harness sent a malformed hook payload.\n"
    )
    raise SystemExit(UNREADABLE_EXIT)


def _stdin_text() -> str:
    buffer = getattr(sys.stdin, "buffer", None)
    return buffer.read().decode("utf-8") if buffer is not None else sys.stdin.read()


def read_hook_payload(hook: str) -> dict[str, object]:
    try:
        payload = json.loads(_stdin_text())
    except (UnicodeDecodeError, ValueError) as exc:
        refuse_unreadable(hook, f"stdin is not UTF-8 JSON ({type(exc).__name__})")
    if not isinstance(payload, dict):
        refuse_unreadable(hook, "the payload is not a JSON object")
    tool_input = payload.get("tool_input", payload.get("input"))
    if tool_input is not None and not isinstance(tool_input, dict):
        refuse_unreadable(hook, "tool_input is not an object")
    wrong = [
        name
        for name in STRING_FIELDS
        if (tool_input or {}).get(name) is not None
        and not isinstance((tool_input or {}).get(name), str)
    ]
    if wrong:
        refuse_unreadable(hook, f"tool_input.{wrong[0]} is not a string")
    if not _edits_are_well_formed((tool_input or {}).get("edits")):
        refuse_unreadable(hook, "tool_input.edits is not a list of edit objects")
    return {**payload, "tool_input": tool_input or {}, "input": tool_input or {}}


def read_advisory_payload(hook: str) -> dict[str, object]:
    try:
        payload = json.loads(_stdin_text())
    except (UnicodeDecodeError, ValueError) as error:
        sys.stderr.write(f"{hook}: unreadable payload: {error}\n")
        return {}
    if not isinstance(payload, dict):
        sys.stderr.write(f"{hook}: payload is not a JSON object\n")
        return {}
    return payload


def _edits_are_well_formed(edits: object) -> bool:
    if edits is None:
        return True
    return isinstance(edits, list) and all(
        isinstance(edit, dict)
        and isinstance(edit.get("new_string", ""), str)
        and isinstance(edit.get("old_string", ""), str)
        for edit in edits
    )


def tool_input_of(payload: dict[str, object]) -> dict[str, object]:
    tool_input = payload.get("tool_input")
    return tool_input if isinstance(tool_input, dict) else {}
