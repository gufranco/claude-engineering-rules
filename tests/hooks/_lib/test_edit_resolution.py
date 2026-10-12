from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.edit_resolution import (  # noqa: E402
    MAX_RESOLVE_BYTES,
    ProposedChange,
    payload_fragments,
    read_source,
    resolved_change,
)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "a.py"
    path.write_text("x = 1\ny = 1\n", encoding="utf-8")
    return path


def test_resolves_a_write_over_an_existing_file(source: Path) -> None:
    # Arrange
    payload = {"file_path": str(source), "content": "z = 1\n"}

    # Act
    change = resolved_change("Write", payload)

    # Assert
    assert change == ProposedChange(str(source), "x = 1\ny = 1\n", "z = 1\n")


def test_resolves_a_write_of_a_new_file_against_an_empty_before(tmp_path: Path) -> None:
    # Arrange
    payload = {"file_path": str(tmp_path / "new.py"), "content": "z = 1\n"}

    # Act
    change = resolved_change("Write", payload)

    # Assert
    assert change == ProposedChange(str(tmp_path / "new.py"), "", "z = 1\n")


def test_resolves_an_edit_with_replace_all(source: Path) -> None:
    # Arrange
    payload = {
        "file_path": str(source),
        "old_string": "1",
        "new_string": "2",
        "replace_all": True,
    }

    # Act
    change = resolved_change("Edit", payload)

    # Assert
    assert change == ProposedChange(str(source), "x = 1\ny = 1\n", "x = 2\ny = 2\n")


def test_resolves_a_multiedit_in_sequence(source: Path) -> None:
    # Arrange
    payload = {
        "file_path": str(source),
        "edits": [
            {"old_string": "x = 1", "new_string": "x = 5"},
            {"old_string": "x = 5", "new_string": "x = 6"},
        ],
    }

    # Act
    change = resolved_change("MultiEdit", payload)

    # Assert
    assert change == ProposedChange(str(source), "x = 1\ny = 1\n", "x = 6\ny = 1\n")


@pytest.mark.parametrize(
    ("tool", "payload"),
    [
        ("Edit", {"old_string": "absent", "new_string": "q"}),
        ("Edit", {"old_string": "", "new_string": "q"}),
        ("Edit", {"old_string": "x", "new_string": 5}),
        ("MultiEdit", {"edits": []}),
        ("MultiEdit", {"edits": ["not a dict"]}),
        ("MultiEdit", {"edits": [{"old_string": "absent", "new_string": "q"}]}),
        ("Read", {}),
        ("Write", {"content": 5}),
    ],
)
def test_returns_none_for_an_unresolvable_payload(
    source: Path, tool: str, payload: dict[str, object]
) -> None:
    # Arrange
    full = {"file_path": str(source), **payload}

    # Act
    change = resolved_change(tool, full)

    # Assert
    assert change is None


def test_returns_none_for_an_edit_of_a_missing_file(tmp_path: Path) -> None:
    # Arrange
    payload = {
        "file_path": str(tmp_path / "gone.py"),
        "old_string": "a",
        "new_string": "b",
    }

    # Act
    change = resolved_change("Edit", payload)

    # Assert
    assert change is None


def test_reads_nothing_past_the_size_ceiling(tmp_path: Path) -> None:
    # Arrange
    path = tmp_path / "huge.py"
    path.write_text("x" * (MAX_RESOLVE_BYTES + 1), encoding="utf-8")

    # Act
    text = read_source(str(path))

    # Assert
    assert text is None


def test_reads_nothing_from_a_binary_file(tmp_path: Path) -> None:
    # Arrange
    path = tmp_path / "blob.py"
    path.write_bytes(b"\xff\xfe\x00")

    # Act
    text = read_source(str(path))

    # Assert
    assert text is None


@pytest.mark.parametrize(
    ("tool", "payload", "expected"),
    [
        ("Write", {"content": "a"}, [("content", "a")]),
        ("Edit", {"new_string": "b"}, [("new_string", "b")]),
        (
            "MultiEdit",
            {"edits": [{"new_string": "c"}, {"new_string": 4}, "junk"]},
            [("edits[0].new_string", "c")],
        ),
        ("Write", {"content": 3}, []),
        ("Read", {}, []),
    ],
)
def test_lists_the_payload_fragments(
    tool: str, payload: dict[str, object], expected: list[tuple[str, str]]
) -> None:
    # Arrange
    candidate = dict(payload)

    # Act
    fragments = payload_fragments(tool, candidate)

    # Assert
    assert fragments == expected
