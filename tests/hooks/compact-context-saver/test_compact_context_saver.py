"""Tests for `hooks/compact-context-saver.py`.


Observable behavior:
- `pre`: writes a snapshot file containing the timestamp, current branch, and
  porcelain git status to `~/.claude/.compact-context`.
- `post`: reads the snapshot file and prints it to stdout under a context
  header. No-op if the file does not exist.
- Bypass via env or file registry skips both branches.
- Unknown subcommand exits 1 with usage on stderr.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "compact-context-saver.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402

_TESTS_DIR = ROOT / "tests"
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _helpers.cov_env import apply_coverage_env  # noqa: E402


def _run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        input="",
        capture_output=True,
        text=True,
        env=apply_coverage_env(merged),
        timeout=5,
    )


def test_pre_writes_snapshot(tmp_path: Path) -> None:
    # Arrange
    snapshot = tmp_path / "snapshot"
    # Act
    result = _run("pre", env={"CLAUDE_COMPACT_CONTEXT": str(snapshot)})
    # Assert
    assert result.returncode == 0
    assert snapshot.exists()
    body = snapshot.read_text(encoding="utf-8")
    assert "Compact Context Snapshot" in body
    assert "Timestamp:" in body
    assert "Branch:" in body


def test_post_emits_saved_context(tmp_path: Path) -> None:
    # Arrange
    snapshot = tmp_path / "snapshot"
    snapshot.write_text(
        "=== Compact Context Snapshot ===\nTimestamp: x\n", encoding="utf-8"
    )
    # Act
    result = _run("post", env={"CLAUDE_COMPACT_CONTEXT": str(snapshot)})
    # Assert
    assert result.returncode == 0
    assert "Context preserved before compaction:" in result.stdout
    assert "=== Compact Context Snapshot ===" in result.stdout


def test_post_silent_when_snapshot_missing(tmp_path: Path) -> None:
    # Arrange
    snapshot = tmp_path / "missing"
    # Act
    result = _run("post", env={"CLAUDE_COMPACT_CONTEXT": str(snapshot)})
    # Assert
    assert result.returncode == 0
    assert result.stdout == ""


def test_default_subcommand_is_pre(tmp_path: Path) -> None:
    # Arrange
    snapshot = tmp_path / "snapshot"
    # Act
    result = _run(env={"CLAUDE_COMPACT_CONTEXT": str(snapshot)})
    # Assert
    assert result.returncode == 0
    assert snapshot.exists()


def test_unknown_subcommand_fails(tmp_path: Path) -> None:
    # Arrange
    # Act
    result = _run("middle", env={"CLAUDE_COMPACT_CONTEXT": str(tmp_path / "x")})
    # Assert
    assert result.returncode == 1
    assert "Usage" in result.stderr


def test_env_disable_skips_pre(tmp_path: Path) -> None:
    # Arrange
    snapshot = tmp_path / "snapshot"
    # Act
    result = _run(
        "pre",
        env={"CLAUDE_COMPACT_CONTEXT": str(snapshot), "COMPACT_CONTEXT_DISABLE": "1"},
    )
    # Assert
    assert result.returncode == 0
    assert not snapshot.exists()


def test_file_bypass_skips_post(tmp_path: Path) -> None:
    # Arrange
    snapshot = tmp_path / "snapshot"
    snapshot.write_text("=== Compact Context Snapshot ===\n", encoding="utf-8")
    state = tmp_path / "state.json"
    set_bypass("compact-context-saver", ttl_seconds=120, state_path=state)
    # Act
    result = _run(
        "post",
        env={
            "CLAUDE_COMPACT_CONTEXT": str(snapshot),
            "CLAUDE_BYPASS_STATE": str(state),
        },
    )
    # Assert
    assert result.returncode == 0
    assert result.stdout == ""


def test_pre_handles_non_git_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    snapshot = tmp_path / "snapshot"
    monkeypatch.chdir(tmp_path)
    # Act
    result = _run("pre", env={"CLAUDE_COMPACT_CONTEXT": str(snapshot)})
    # Assert
    assert result.returncode == 0
    body = snapshot.read_text(encoding="utf-8")
    assert "Branch:" in body


def test_git_branch_falls_back_when_git_missing(tmp_path: Path) -> None:
    # Arrange
    snapshot = tmp_path / "snapshot"
    bin_dir = tmp_path / "empty-bin"
    bin_dir.mkdir()
    # Act: PATH without git triggers FileNotFoundError -> "unknown"
    result = subprocess.run(
        [sys.executable, str(HOOK), "pre"],
        input="",
        capture_output=True,
        text=True,
        env=apply_coverage_env(
            {"CLAUDE_COMPACT_CONTEXT": str(snapshot), "PATH": str(bin_dir)}
        ),
        timeout=5,
    )
    # Assert
    assert result.returncode == 0
    body = snapshot.read_text(encoding="utf-8")
    assert "Branch: unknown" in body
    assert "not a git repo" in body


def test_git_status_non_zero_returncode(tmp_path: Path) -> None:
    # Arrange: simulate `git` that always exits non-zero
    snapshot = tmp_path / "snapshot"
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    fake_git = bin_dir / "git"
    fake_git.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    fake_git.chmod(0o755)
    # Act
    result = subprocess.run(
        [sys.executable, str(HOOK), "pre"],
        input="",
        capture_output=True,
        text=True,
        env=apply_coverage_env(
            {"CLAUDE_COMPACT_CONTEXT": str(snapshot), "PATH": str(bin_dir)}
        ),
        timeout=5,
    )
    # Assert
    assert result.returncode == 0
    body = snapshot.read_text(encoding="utf-8")
    assert "not a git repo" in body
