from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[3] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.dangerous_command_push import (  # noqa: E402
    git_push_directory,
    names_protected_ref,
    repo_root,
)


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["git", "push"], (True, "/base")),
        (["git", "-C", "sub", "push"], (True, "/base/sub")),
        (["git", "--git-dir=/x", "push"], (True, None)),
        (["git", "status"], (False, "/base")),
    ],
)
def test_git_push_directory_resolves_the_push_target(
    args: list[str], expected: tuple[bool, str | None]
) -> None:
    # Arrange
    base = "/base"

    # Act
    result = git_push_directory(args, base)

    # Assert
    assert result == expected


def test_names_protected_ref_ignores_feature_branches() -> None:
    # Arrange
    text = " feature/main-menu"

    # Act
    result = names_protected_ref(text)

    # Assert
    assert result is False


def test_repo_root_outside_a_repository_is_empty(tmp_path: Path) -> None:
    # Arrange
    directory = str(tmp_path)

    # Act
    result = repo_root(directory)

    # Assert
    assert result == ""
