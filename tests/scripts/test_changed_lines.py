from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.changed_lines import changed_lines, parse_hunks  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@test.local",
            *args,
        ],
        check=True,
        capture_output=True,
    )


def _repo_with(tmp_path: Path, name: str, text: str) -> Path:
    _git(tmp_path, "init", "-q")
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    _git(tmp_path, "add", name)
    _git(tmp_path, "commit", "-q", "--no-gpg-sign", "-m", "base")
    return target


def test_parse_hunks_reads_added_ranges():
    # Arrange
    diff = (
        "@@ -1,0 +2,3 @@\n+a\n+b\n+c\n@@ -9 +12 @@\n-x\n+y\n@@ -20,2 +23,0 @@\n-gone\n"
    )

    # Act
    lines = parse_hunks(diff)

    # Assert
    assert lines == frozenset({2, 3, 4, 12})


def test_changed_lines_reports_only_edited_lines(tmp_path):
    # Arrange
    target = _repo_with(tmp_path, "a.c", "int a;\nint b;\nint c;\n")
    target.write_text("int a;\nint bb;\nint c;\nint d;\n", encoding="utf-8")

    # Act
    lines = changed_lines(target)

    # Assert
    assert lines == frozenset({2, 4})


def test_changed_lines_treats_an_untracked_file_as_all_new(tmp_path):
    # Arrange
    _repo_with(tmp_path, "a.c", "int a;\n")
    fresh = tmp_path / "b.c"
    fresh.write_text("int b;\n", encoding="utf-8")

    # Act
    lines = changed_lines(fresh)

    # Assert
    assert lines is None


def test_changed_lines_treats_a_file_outside_git_as_all_new(tmp_path):
    # Arrange
    loose = tmp_path / "loose.c"
    loose.write_text("int a;\n", encoding="utf-8")

    # Act
    lines = changed_lines(loose)

    # Assert
    assert lines is None


def test_changed_lines_treats_an_unreadable_history_as_all_new(tmp_path):
    # Arrange
    target = _repo_with(tmp_path, "a.c", "int a;\n")
    blob = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD:a.c"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (tmp_path / ".git" / "objects" / blob[:2] / blob[2:]).unlink()
    target.write_text("int b;\n", encoding="utf-8")

    # Act
    lines = changed_lines(target)

    # Assert
    assert lines is None
