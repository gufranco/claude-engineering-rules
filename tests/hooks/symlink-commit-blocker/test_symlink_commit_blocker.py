from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "symlink-commit-blocker.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], check=True, cwd=str(repo), env=GIT_ENV, timeout=30)


@pytest.fixture()
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "real.txt").write_text("real\n")
    _git(repo, "add", "real.txt")
    _git(repo, "commit", "-q", "-m", "init")
    monkeypatch.chdir(repo)
    return repo


def _link(repo: Path, name: str) -> Path:
    target = repo / name
    target.symlink_to("real.txt")
    return target


def test_ignores_non_commit_command(git_repo: Path, tool_use, run_hook) -> None:
    # Arrange
    _link(git_repo, "alias.txt")
    _git(git_repo, "add", "alias.txt")
    payload = tool_use("Bash", {"command": "git status"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_commit_of_regular_files(git_repo: Path, tool_use, run_hook) -> None:
    # Arrange
    (git_repo / "notes.txt").write_text("notes\n")
    _git(git_repo, "add", "notes.txt")
    payload = tool_use("Bash", {"command": "git commit -m msg"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_staged_new_symlink(git_repo: Path, tool_use, run_hook) -> None:
    # Arrange
    _link(git_repo, "alias.txt")
    _git(git_repo, "add", "alias.txt")
    payload = tool_use("Bash", {"command": "git commit -m msg"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "BLOCKED")
    assert "  1 symbolic link(s) would be committed:\n    alias.txt" in stderr
    assert "git rm --cached <link>" in stderr


def test_blocks_file_turned_into_symlink(git_repo: Path, tool_use, run_hook) -> None:
    # Arrange
    (git_repo / "other.txt").write_text("other\n")
    _git(git_repo, "add", "other.txt")
    _git(git_repo, "commit", "-q", "-m", "other")
    (git_repo / "other.txt").unlink()
    _link(git_repo, "other.txt")
    _git(git_repo, "add", "other.txt")
    payload = tool_use("Bash", {"command": "git commit -m msg"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "BLOCKED")
    assert "  other.txt" in stderr


def test_allows_removing_a_committed_symlink(
    git_repo: Path, tool_use, run_hook
) -> None:
    # Arrange
    _link(git_repo, "alias.txt")
    _git(git_repo, "add", "alias.txt")
    _git(git_repo, "commit", "-q", "-m", "link")
    _git(git_repo, "rm", "-q", "alias.txt")
    payload = tool_use("Bash", {"command": "git commit -m msg"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_symlink_added_by_whole_tree_add(
    git_repo: Path, tool_use, run_hook
) -> None:
    # Arrange
    _link(git_repo, "alias.txt")
    payload = tool_use("Bash", {"command": "git add -A && git commit -m msg"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "BLOCKED")
    assert "  alias.txt" in stderr


def test_blocks_symlink_added_by_path_in_same_command(
    git_repo: Path, tool_use, run_hook
) -> None:
    # Arrange
    (git_repo / "docs").mkdir()
    _link(git_repo, "docs/alias.txt")
    payload = tool_use("Bash", {"command": "git add docs && git commit -m msg"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "BLOCKED")
    assert "  docs/alias.txt" in stderr


def test_allows_unrelated_untracked_symlink(git_repo: Path, tool_use, run_hook) -> None:
    # Arrange
    _link(git_repo, "alias.txt")
    (git_repo / "notes.txt").write_text("notes\n")
    payload = tool_use("Bash", {"command": "git add notes.txt && git commit -m msg"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_tracked_file_replaced_by_link_under_commit_all(
    git_repo: Path, tool_use, run_hook
) -> None:
    # Arrange
    (git_repo / "real.txt").unlink()
    (git_repo / "real.txt").symlink_to("missing.txt")
    payload = tool_use("Bash", {"command": "git commit -am msg"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "BLOCKED")
    assert "  real.txt" in stderr


def test_follows_git_dash_c_to_the_named_repository(
    git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool_use, run_hook
) -> None:
    # Arrange
    _link(git_repo, "alias.txt")
    _git(git_repo, "add", "alias.txt")
    monkeypatch.chdir(tmp_path)
    payload = tool_use("Bash", {"command": f"git -C {git_repo} commit -m msg"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "BLOCKED")
    assert "  alias.txt" in stderr


def test_env_disable_short_circuits(git_repo: Path, tool_use, run_hook) -> None:
    # Arrange
    _link(git_repo, "alias.txt")
    _git(git_repo, "add", "alias.txt")
    payload = tool_use("Bash", {"command": "git commit -m msg"})

    # Act
    result = run_hook(HOOK, payload, env={"SYMLINK_COMMIT_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_file_bypass_short_circuits(
    git_repo: Path, tool_use, run_hook, tmp_path: Path
) -> None:
    # Arrange
    _link(git_repo, "alias.txt")
    _git(git_repo, "add", "alias.txt")
    state = tmp_path / "state.json"
    set_bypass("symlink-commit-blocker", ttl_seconds=120, state_path=state)
    payload = tool_use("Bash", {"command": "git commit -m msg"})

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(state)})

    # Assert
    assert_allowed(result)


def test_ignores_commit_outside_a_git_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool_use, run_hook
) -> None:
    # Arrange
    monkeypatch.chdir(tmp_path)
    payload = tool_use("Bash", {"command": "git commit -m msg"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
