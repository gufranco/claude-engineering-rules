"""Tests for `hooks/large-file-blocker.py`.

Observable behavior:
- Ignores non-`git commit` Bash commands.
- Blocks when any staged file exceeds 5 MB; prints offending paths with sizes.
- Allows when staged files are all under the limit or nothing is staged.
- Bypass via env or file registry returns 0 immediately.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "large-file-blocker.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402


@pytest.fixture()
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, env=env)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _stage(repo: Path, name: str, size_bytes: int) -> Path:
    target = repo / name
    target.write_bytes(b"x" * size_bytes)
    subprocess.run(["git", "add", name], check=True, cwd=str(repo))
    return target


def test_ignores_non_commit_command(git_repo: Path, tool_use, assert_allows) -> None:
    # Arrange
    _stage(git_repo, "huge.bin", 6 * 1024 * 1024)
    payload = tool_use("Bash", {"command": "git status"})
    # Act
    assert_allows(HOOK, payload)


def test_allows_small_files(git_repo: Path, tool_use, assert_allows) -> None:
    # Arrange
    _stage(git_repo, "small.txt", 1024)
    payload = tool_use("Bash", {"command": "git commit -m msg"})
    # Act
    assert_allows(HOOK, payload)


def test_blocks_when_staged_file_exceeds_limit(
    git_repo: Path, tool_use, assert_blocks
) -> None:
    # Arrange
    _stage(git_repo, "huge.bin", 6 * 1024 * 1024)
    payload = tool_use("Bash", {"command": "git commit -m msg"})
    # Act
    _code, stderr = assert_blocks(HOOK, payload, "BLOCKED")
    # Assert
    assert "huge.bin" in stderr
    assert "git reset HEAD" in stderr


def test_env_disable_short_circuits(git_repo: Path, tool_use, assert_allows) -> None:
    # Arrange
    _stage(git_repo, "huge.bin", 6 * 1024 * 1024)
    payload = tool_use("Bash", {"command": "git commit -m msg"})
    # Act
    assert_allows(HOOK, payload, env={"LARGE_FILE_DISABLE": "1"})


def test_file_bypass_short_circuits(
    git_repo: Path, tool_use, assert_allows, tmp_path: Path
) -> None:
    # Arrange
    _stage(git_repo, "huge.bin", 6 * 1024 * 1024)
    state = tmp_path / "state.json"
    set_bypass("large-file-blocker", ttl_seconds=120, state_path=state)
    payload = tool_use("Bash", {"command": "git commit -m msg"})
    # Act
    assert_allows(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(state)})


def test_handles_malformed_json(git_repo: Path, run_hook) -> None:
    # Arrange
    # Act
    code, _stdout, _stderr = run_hook(HOOK, {"_raw": "not json"})
    # Assert
    assert code in (0, 2)


def test_ignores_when_outside_git_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool_use, assert_allows
) -> None:
    # Arrange
    monkeypatch.chdir(tmp_path)
    payload = tool_use("Bash", {"command": "git commit -m msg"})
    # Act
    assert_allows(HOOK, payload)


def test_skips_missing_staged_paths(git_repo: Path, tool_use, assert_allows) -> None:
    # Arrange
    target = _stage(git_repo, "tracked.bin", 1024)
    target.unlink()
    payload = tool_use("Bash", {"command": "git commit -m msg"})
    # Act
    assert_allows(HOOK, payload)
