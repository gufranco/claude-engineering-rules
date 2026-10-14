from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest


def test_explicit_add_paths_keeps_quoted_path_with_spaces_intact(hook) -> None:
    # Arrange
    command = "git add src/index.ts 'roms/My Game.sfc'"

    # Act
    result = hook._explicit_add_paths(command)

    # Assert
    assert result == ["src/index.ts", "roms/My Game.sfc"]


def test_explicit_add_paths_falls_back_on_unbalanced_quotes(hook) -> None:
    # Arrange
    command = "git add roms/broken'.sfc"

    # Act
    result = hook._explicit_add_paths(command)

    # Assert
    assert result == ["roms/broken'.sfc"]


def test_explicit_add_paths_sees_through_git_c_redirection(hook) -> None:
    # Arrange
    command = "git -C /repo add roms/game.sfc"

    # Act
    result = hook._explicit_add_paths(command)

    # Assert
    assert result == ["roms/game.sfc"]


def test_commit_pattern_matches_git_c_redirection(hook) -> None:
    # Arrange
    text = "git -C /repo commit -m x"

    # Act
    result = hook.COMMIT_PATTERN.search(text)

    # Assert
    assert result is not None


def test_commit_pattern_ignores_the_word_commit_as_an_argument(hook) -> None:
    # Arrange
    text = "git log --grep commit"

    # Act
    result = hook.COMMIT_PATTERN.search(text)

    # Assert
    assert result is None


def test_explicit_add_paths_drops_flags_and_bulk_selectors(hook) -> None:
    # Arrange
    command = "git add -A . --update"

    # Act
    result = hook._explicit_add_paths(command)

    # Assert
    assert result == []


def test_explicit_add_paths_ignores_other_git_subcommands(hook) -> None:
    # Arrange
    command = "git status && git log --oneline"

    # Act
    result = hook._explicit_add_paths(command)

    # Assert
    assert result == []


def test_repo_root_falls_back_to_cwd_outside_a_repo(
    hook: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.chdir(tmp_path)

    # Act
    result = hook._repo_root()

    # Assert
    assert result.resolve() == tmp_path.resolve()


def test_repo_root_uses_git_toplevel_from_a_subdirectory(
    hook: ModuleType, git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    nested = git_repo / "packages" / "core"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    # Act
    result = hook._repo_root()

    # Assert
    assert result.resolve() == git_repo.resolve()
