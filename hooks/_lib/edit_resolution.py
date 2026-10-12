from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

MAX_RESOLVE_BYTES = 512 * 1024


@dataclass(frozen=True, slots=True)
class ProposedChange:
    path: str
    before: str
    after: str


def read_source(path: str) -> str | None:
    try:
        if os.path.getsize(path) > MAX_RESOLVE_BYTES:
            return None
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def _apply_edit(text: str, edit: Mapping[str, object]) -> str | None:
    old = edit.get("old_string")
    new = edit.get("new_string")
    if not isinstance(old, str) or not isinstance(new, str) or not old:
        return None
    if old not in text:
        return None
    count = -1 if edit.get("replace_all") else 1
    return text.replace(old, new, count)


def _apply_edits(text: str, edits: object) -> str | None:
    if not isinstance(edits, list) or not edits:
        return None
    current: str | None = text
    for edit in edits:
        if current is None or not isinstance(edit, Mapping):
            return None
        current = _apply_edit(current, edit)
    return current


def resolved_change(
    tool: str, tool_input: Mapping[str, object]
) -> ProposedChange | None:
    path = str(tool_input.get("file_path") or "")
    if tool == "Write":
        content = tool_input.get("content")
        if not isinstance(content, str):
            return None
        return ProposedChange(path, read_source(path) or "", content)
    if tool not in ("Edit", "MultiEdit"):
        return None
    before = read_source(path)
    if before is None:
        return None
    after = (
        _apply_edit(before, tool_input)
        if tool == "Edit"
        else _apply_edits(before, tool_input.get("edits"))
    )
    return None if after is None else ProposedChange(path, before, after)


def payload_fragments(
    tool: str, tool_input: Mapping[str, object]
) -> list[tuple[str, str]]:
    if tool == "Write":
        content = tool_input.get("content")
        return [("content", content)] if isinstance(content, str) else []
    if tool == "Edit":
        text = tool_input.get("new_string")
        return [("new_string", text)] if isinstance(text, str) else []
    if tool != "MultiEdit":
        return []
    edits = tool_input.get("edits")
    return [
        (f"edits[{index}].new_string", edit["new_string"])
        for index, edit in enumerate(edits if isinstance(edits, list) else [])
        if isinstance(edit, Mapping) and isinstance(edit.get("new_string"), str)
    ]
