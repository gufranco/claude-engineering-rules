from __future__ import annotations

import re
from pathlib import Path

ASSERTION_RE = re.compile(
    r"\bexpect\s*\("
    r"|\bassert(?:_\w+|[A-Z]\w*)?!?(?=[\s(])"
    r"|\bassert\.\w+\s*\("
    r"|\bXCTAssert\w*\s*\("
    r"|\bpytest\.raises\b"
    r"|\.should\b"
    r"|\bt\.(?:Error|Errorf|Fatal|Fatalf)\s*\("
    r"|\brequire\.\w+\s*\("
)

TEST_CASE_RE = re.compile(
    r"^\s*(?:"
    r"(?:async\s+)?def\s+test_\w+"
    r"|func\s+Test\w+"
    r"|(?:it|test)(?:\.each\([^)]*\))?\s*\("
    r"|#\[test\]"
    r")",
    re.MULTILINE,
)

SKIP_RE = re.compile(
    r"^\s*(?:"
    r"(?:it|test|describe)\.(?:skip|todo)\b"
    r"|x(?:it|test|describe)\s*\("
    r"|@pytest\.mark\.(?:skip|xfail)\b"
    r"|@unittest\.skip\w*\b"
    r"|t\.Skip\w*\s*\("
    r"|#\[ignore\]"
    r")",
    re.MULTILINE,
)

MEASURES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("assertions", ASSERTION_RE, "drop"),
    ("test cases", TEST_CASE_RE, "drop"),
    ("skip markers", SKIP_RE, "rise"),
)

UNREADABLE = "the existing test file could not be read to compare against"


def _weakened(direction: str, old: int, new: int) -> bool:
    return new < old if direction == "drop" else new > old


def weakening_findings(before: str, after: str) -> list[str]:
    counts = [
        (label, direction, len(pattern.findall(before)), len(pattern.findall(after)))
        for label, pattern, direction in MEASURES
    ]
    return [
        f"{label} {direction} from {old} to {new}"
        for label, direction, old, new in counts
        if _weakened(direction, old, new)
    ]


def _current_text(path: Path) -> str | None:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _multiedit_sides(tool_input: dict[str, object]) -> tuple[str, str]:
    raw = tool_input.get("edits")
    edits = (
        [edit for edit in raw if isinstance(edit, dict)]
        if isinstance(raw, list)
        else []
    )
    before = "\n".join(str(edit.get("old_string", "")) for edit in edits)
    after = "\n".join(str(edit.get("new_string", "")) for edit in edits)
    return before, after


def edit_sides(tool_name: str, tool_input: dict[str, object]) -> tuple[str, str] | None:
    if tool_name == "Edit":
        return str(tool_input.get("old_string", "")), str(
            tool_input.get("new_string", "")
        )
    if tool_name == "MultiEdit":
        return _multiedit_sides(tool_input)
    if tool_name != "Write":
        return "", ""
    current = _current_text(Path(str(tool_input.get("file_path", ""))))
    if current is None:
        return None
    return current, str(tool_input.get("content", ""))


def findings_for(tool_name: str, tool_input: dict[str, object]) -> list[str]:
    sides = edit_sides(tool_name, tool_input)
    if sides is None:
        return [UNREADABLE]
    return weakening_findings(*sides)
