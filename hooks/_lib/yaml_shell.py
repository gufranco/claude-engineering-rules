from __future__ import annotations

import re

TextRange = tuple[int, int]

SHELL_KEY = re.compile(
    r"^(?P<indent>[ \t]*)(?:-[ \t]+)?"
    r"(?P<key>run|script|before_script|after_script|command|entrypoint|entry|cmds)"
    r"[ \t]*:(?:[ \t]+(?P<value>[^\n]*?))?[ \t]*$"
)
LIST_ITEM = re.compile(r"^[ \t]*-[ \t]+(?:cmd[ \t]*:[ \t]*)?(?P<value>[^\n]*?)[ \t]*$")
BLOCK_INDICATOR = re.compile(r"^[|>][-+1-9]{0,2}(?:[ \t]+#.*)?$")
LIST_KEYS = frozenset({"script", "before_script", "after_script", "cmds"})
FLOW_OPENERS = ("[", "{")
QUOTES = ("'", '"')
NON_SHELL_ITEM = "task:"


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def _nested_end(lines: list[str], first: int, parent: int) -> int:
    index = first
    while index < len(lines) and (
        not lines[index].strip() or _indent_of(lines[index]) > parent
    ):
        index += 1
    return index


def _scalar_range(line_start: int, line: str, column: int) -> TextRange | None:
    value = line[column:].rstrip()
    if not value or value.startswith(FLOW_OPENERS):
        return None
    if value[0] in QUOTES:
        close = value.rfind(value[0])
        return (line_start + column + 1, line_start + column + max(close, 1))
    return (line_start + column, line_start + column + len(value))


def _value_ranges(
    lines: list[str], starts: list[int], index: int, column: int
) -> tuple[list[TextRange], int]:
    value = lines[index][column:].strip()
    if not BLOCK_INDICATOR.match(value):
        scalar = _scalar_range(starts[index], lines[index], column)
        return ([scalar] if scalar else []), index + 1
    end = _nested_end(lines, index + 1, _indent_of(lines[index]))
    if end == index + 1:
        return [], end
    return [(starts[index + 1], starts[end - 1] + len(lines[end - 1]))], end


def _list_ranges(
    lines: list[str], starts: list[int], index: int, parent: int
) -> tuple[list[TextRange], int]:
    ranges: list[TextRange] = []
    end = _nested_end(lines, index + 1, parent)
    cursor = index + 1
    while cursor < end:
        item = LIST_ITEM.match(lines[cursor])
        if item is None or item.group("value").startswith(NON_SHELL_ITEM):
            cursor += 1
            continue
        found, cursor = _value_ranges(lines, starts, cursor, item.start("value"))
        ranges.extend(found)
    return ranges, end


def yaml_shell_ranges(text: str, starts: list[int]) -> list[TextRange]:
    lines = text.split("\n")
    ranges: list[TextRange] = []
    index = 0
    while index < len(lines):
        match = SHELL_KEY.match(lines[index])
        if match is None:
            index += 1
            continue
        if match.group("value"):
            found, index = _value_ranges(lines, starts, index, match.start("value"))
        elif match.group("key") in LIST_KEYS:
            found, index = _list_ranges(
                lines, starts, index, len(match.group("indent"))
            )
        else:
            found, index = [], index + 1
        ranges.extend(found)
    return ranges
