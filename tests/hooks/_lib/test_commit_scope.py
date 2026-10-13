from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.commit_scope import add_scope, commits_all, repo_dir, within  # noqa: E402


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("cd sub && git commit -m x", "/base/sub"),
        ("git -C /elsewhere commit -m x", "/elsewhere"),
        ("git commit -m x", "/base"),
    ],
)
def test_repo_dir_follows_cd_and_dash_c(command, expected):
    # Arrange
    cwd = "/base"

    # Act
    result = repo_dir(command, cwd)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git add a.txt b/ && git commit -m x", (False, ["a.txt", "b/"])),
        ("git add -A && git commit -m x", (True, [])),
        ("git commit -m x", (False, [])),
    ],
)
def test_add_scope_reads_what_the_command_stages(command, expected):
    # Arrange
    text = command

    # Act
    result = add_scope(text)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git commit -am x", True),
        ("git commit --all -m x", True),
        ("git commit -m x", False),
    ],
)
def test_commits_all_detects_the_all_flag(command, expected):
    # Arrange
    text = command

    # Act
    result = commits_all(text)

    # Assert
    assert result is expected


def test_within_matches_files_and_directories():
    # Arrange
    paths = ["./src/", "README.md"]

    # Act
    result = [within(name, paths) for name in ("src/a.py", "README.md", "srcx/a.py")]

    # Assert
    assert result == [True, True, False]
