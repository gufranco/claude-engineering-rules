from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "large-file-blocker"
BIG = 6 * 1024 * 1024


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@test.local", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "small.txt").write_text("x", encoding="utf-8")
    _git(root, "add", "small.txt")
    _git(root, "commit", "-q", "--no-verify", "-m", "chore: start")
    return root


def _bash(tool_use, command: str, cwd: Path):
    return tool_use("Bash", {"command": command}, cwd=str(cwd))


def test_a_large_file_added_in_the_same_command_is_blocked(tool_use, run_hook, repo):
    # Arrange
    (repo / "big.bin").write_bytes(b"\0" * BIG)
    payload = _bash(tool_use, "git add big.bin && git commit -m 'feat: x'", repo)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "big.bin")


def test_a_large_tracked_change_committed_with_all_is_blocked(
    tool_use, run_hook, repo, tmp_path
):
    # Arrange
    (repo / "small.txt").write_bytes(b"\0" * BIG)
    payload = _bash(tool_use, f"git -C {repo} commit -am 'feat: x'", tmp_path)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "small.txt")


def test_the_staged_blob_counts_even_when_the_file_shrank(tool_use, run_hook, repo):
    # Arrange
    (repo / "big.bin").write_bytes(b"\0" * BIG)
    _git(repo, "add", "big.bin")
    (repo / "big.bin").write_text("tiny", encoding="utf-8")
    payload = _bash(tool_use, "git commit -m 'feat: x'", repo)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "big.bin")


def test_a_small_commit_is_allowed(tool_use, run_hook, repo):
    # Arrange
    (repo / "small.txt").write_text("y", encoding="utf-8")
    payload = _bash(tool_use, "git commit -am 'fix: y'", repo)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
