from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import project_scope as ps  # noqa: E402


def make_repo(root: Path) -> Path:
    (root / ".git").mkdir(parents=True, exist_ok=True)
    return root


def test_repo_root_finds_the_enclosing_repository(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    nested = repo / "src" / "deep"
    nested.mkdir(parents=True)

    # Act
    result = ps.repo_root(nested)

    # Assert
    assert result == repo


def test_repo_root_returns_the_directory_itself_when_it_holds_git(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")

    # Act
    result = ps.repo_root(repo)

    # Assert
    assert result == repo


def test_repo_root_returns_none_outside_any_repository(tmp_path):
    # Arrange
    loose = tmp_path / "loose"
    loose.mkdir()

    # Act
    result = ps.repo_root(loose)

    # Assert
    assert result is None


def test_repo_root_stops_at_the_nearest_repository(tmp_path):
    # Arrange
    outer = make_repo(tmp_path / "outer")
    inner = make_repo(outer / "inner")
    nested = inner / "src"
    nested.mkdir(parents=True)

    # Act
    result = ps.repo_root(nested)

    # Assert
    assert result == inner


def test_repo_root_tolerates_a_git_file_from_a_worktree(tmp_path):
    # Arrange
    repo = tmp_path / "worktree"
    repo.mkdir()
    (repo / ".git").write_text("gitdir: /elsewhere/.git/worktrees/wt\n")
    nested = repo / "src"
    nested.mkdir()

    # Act
    result = ps.repo_root(nested)

    # Assert
    assert result == repo


def test_walk_up_stops_at_the_repository_root(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    nested = repo / "a" / "b"
    nested.mkdir(parents=True)

    # Act
    visited = list(ps.walk_up(nested, limit=10))

    # Assert
    assert visited == [nested, repo / "a", repo]


def test_walk_up_respects_the_limit(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    nested = repo / "a" / "b" / "c"
    nested.mkdir(parents=True)

    # Act
    visited = list(ps.walk_up(nested, limit=2))

    # Assert
    assert visited == [nested, repo / "a" / "b"]


def test_walk_up_outside_a_repository_still_bounded_by_the_limit(tmp_path):
    # Arrange
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    # Act
    visited = list(ps.walk_up(nested, limit=3))

    # Assert
    assert len(visited) == 3
    assert visited[0] == nested


def test_walk_up_can_cross_the_boundary_when_asked(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    nested = repo / "a"
    nested.mkdir(parents=True)

    # Act
    visited = list(ps.walk_up(nested, limit=3, stop_at_repo_root=False))

    # Assert
    assert repo.parent in visited


def test_walk_up_terminates_at_the_filesystem_root():
    # Arrange
    start = Path("/")

    # Act
    visited = list(ps.walk_up(start, limit=5))

    # Assert
    assert visited == [Path("/")]
