from __future__ import annotations

import re
import subprocess
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
GIT_TIMEOUT_SECONDS = 5


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


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _committed_text(path: Path) -> str | None:
    top = _git(path.parent, "rev-parse", "--show-toplevel")
    if top is None or top.returncode != 0:
        return None
    relative = path.resolve().relative_to(Path(top.stdout.strip()).resolve())
    shown = _git(path.parent, "show", f"HEAD:{relative.as_posix()}")
    if shown is None:
        return None
    return shown.stdout if shown.returncode == 0 else ""


def _apply(text: str, edit: dict[str, object]) -> str | None:
    old = str(edit.get("old_string", ""))
    new = str(edit.get("new_string", ""))
    if not old or old not in text:
        return None
    return text.replace(old, new, -1 if edit.get("replace_all") is True else 1)


def _edited_text(
    tool_name: str, tool_input: dict[str, object], text: str
) -> str | None:
    if tool_name == "Write":
        return str(tool_input.get("content", ""))
    raw = tool_input.get("edits") if tool_name == "MultiEdit" else [tool_input]
    edits = [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []
    result: str | None = text
    for edit in edits:
        result = _apply(result, edit) if result is not None else None
    return result


def no_weaker_than_commit(tool_name: str, tool_input: dict[str, object]) -> bool:
    path = Path(str(tool_input.get("file_path", "")))
    current = _current_text(path)
    committed = _committed_text(path)
    if current is None or committed is None:
        return False
    after = _edited_text(tool_name, tool_input, current)
    return after is not None and not weakening_findings(committed, after)


def findings_for(tool_name: str, tool_input: dict[str, object]) -> list[str]:
    sides = edit_sides(tool_name, tool_input)
    if sides is None:
        return [UNREADABLE]
    findings = weakening_findings(*sides)
    if findings and no_weaker_than_commit(tool_name, tool_input):
        return []
    return findings
