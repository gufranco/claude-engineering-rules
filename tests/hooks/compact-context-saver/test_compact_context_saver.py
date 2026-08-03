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
import time
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


def _run(
    *args: str, env: dict | None = None, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        input="",
        capture_output=True,
        text=True,
        env=apply_coverage_env(merged),
        cwd=str(cwd) if cwd else None,
        timeout=5,
    )


def _snapshot_for(project: Path, *, timestamp: str = "2026-08-03 12:00:00 GMT") -> str:
    return (
        "=== Compact Context Snapshot ===\n"
        f"Timestamp: {timestamp}\n"
        f"Project: {Path(project).resolve()}\n"
        "Session: abc123\n"
        "Branch: main\n"
        "\n"
        "Modified files:\n"
        " M src/example.py\n"
    )


def test_pre_writes_snapshot(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    result = _run("pre", env={"CLAUDE_COMPACT_CONTEXT": str(snapshot)})
    assert result.returncode == 0
    assert snapshot.exists()
    body = snapshot.read_text(encoding="utf-8")
    assert "Compact Context Snapshot" in body
    assert "Timestamp:" in body
    assert "Branch:" in body


def test_post_emits_saved_context(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    snapshot = tmp_path / "snapshot"
    snapshot.write_text(_snapshot_for(project), encoding="utf-8")

    result = _run("post", env={"CLAUDE_COMPACT_CONTEXT": str(snapshot)}, cwd=project)

    assert result.returncode == 0
    assert "Context preserved before compaction:" in result.stdout
    assert "=== Compact Context Snapshot ===" in result.stdout


def test_post_is_silent_when_the_snapshot_belongs_to_another_project(
    tmp_path: Path,
) -> None:
    mine = tmp_path / "minerva"
    theirs = tmp_path / "aesmovie"
    mine.mkdir()
    theirs.mkdir()
    snapshot = tmp_path / "snapshot"
    snapshot.write_text(_snapshot_for(theirs), encoding="utf-8")

    result = _run("post", env={"CLAUDE_COMPACT_CONTEXT": str(snapshot)}, cwd=mine)

    assert result.returncode == 0
    assert result.stdout == ""


def test_post_is_silent_for_a_legacy_snapshot_without_a_project_line(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    snapshot = tmp_path / "snapshot"
    snapshot.write_text(
        "=== Compact Context Snapshot ===\nTimestamp: x\nBranch: main\n",
        encoding="utf-8",
    )

    result = _run("post", env={"CLAUDE_COMPACT_CONTEXT": str(snapshot)}, cwd=project)

    assert result.returncode == 0
    assert result.stdout == ""


def test_post_is_silent_when_the_snapshot_is_stale(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    snapshot = tmp_path / "snapshot"
    snapshot.write_text(_snapshot_for(project), encoding="utf-8")
    ancient = time.time() - (48 * 60 * 60)
    os.utime(snapshot, (ancient, ancient))

    result = _run("post", env={"CLAUDE_COMPACT_CONTEXT": str(snapshot)}, cwd=project)

    assert result.returncode == 0
    assert result.stdout == ""


def test_pre_records_the_project_root_and_session(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    snapshot = tmp_path / "snapshot"

    result = _run(
        "pre",
        env={
            "CLAUDE_COMPACT_CONTEXT": str(snapshot),
            "CLAUDE_CODE_SESSION_ID": "sess-42",
        },
        cwd=project,
    )

    assert result.returncode == 0
    body = snapshot.read_text(encoding="utf-8")
    assert f"Project: {project.resolve()}" in body
    assert "Session: sess-42" in body


def test_pre_and_post_round_trip_within_one_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    snapshot = tmp_path / "snapshot"

    _run("pre", env={"CLAUDE_COMPACT_CONTEXT": str(snapshot)}, cwd=project)
    result = _run("post", env={"CLAUDE_COMPACT_CONTEXT": str(snapshot)}, cwd=project)

    assert result.returncode == 0
    assert "Context preserved before compaction:" in result.stdout


def test_default_snapshot_path_is_distinct_per_project(tmp_path: Path) -> None:
    home = tmp_path / "home"
    first = tmp_path / "project-one"
    second = tmp_path / "project-two"
    for directory in (home, first, second):
        directory.mkdir()
    env = {"HOME": str(home), "CLAUDE_COMPACT_CONTEXT": ""}

    _run("pre", env=env, cwd=first)
    _run("pre", env=env, cwd=second)

    written = sorted((home / ".claude" / ".compact-context.d").glob("*.snapshot"))
    assert len(written) == 2


def test_default_post_ignores_a_snapshot_written_by_another_project(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    first = tmp_path / "project-one"
    second = tmp_path / "project-two"
    for directory in (home, first, second):
        directory.mkdir()
    env = {"HOME": str(home), "CLAUDE_COMPACT_CONTEXT": ""}

    _run("pre", env=env, cwd=first)
    result = _run("post", env=env, cwd=second)

    assert result.returncode == 0
    assert result.stdout == ""


def test_pre_retires_the_legacy_global_snapshot(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"
    for directory in (home, project):
        directory.mkdir()
    legacy = home / ".claude" / ".compact-context"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        "=== Compact Context Snapshot ===\nBranch: other\n", encoding="utf-8"
    )

    result = _run(
        "pre", env={"HOME": str(home), "CLAUDE_COMPACT_CONTEXT": ""}, cwd=project
    )

    assert result.returncode == 0
    assert not legacy.exists()


def test_post_silent_when_snapshot_missing(tmp_path: Path) -> None:
    snapshot = tmp_path / "missing"
    result = _run("post", env={"CLAUDE_COMPACT_CONTEXT": str(snapshot)})
    assert result.returncode == 0
    assert result.stdout == ""


def test_default_subcommand_is_pre(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    result = _run(env={"CLAUDE_COMPACT_CONTEXT": str(snapshot)})
    assert result.returncode == 0
    assert snapshot.exists()


def test_unknown_subcommand_fails(tmp_path: Path) -> None:
    result = _run("middle", env={"CLAUDE_COMPACT_CONTEXT": str(tmp_path / "x")})
    assert result.returncode == 1
    assert "Usage" in result.stderr


def test_env_disable_skips_pre(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    result = _run(
        "pre",
        env={"CLAUDE_COMPACT_CONTEXT": str(snapshot), "COMPACT_CONTEXT_DISABLE": "1"},
    )
    assert result.returncode == 0
    assert not snapshot.exists()


def test_file_bypass_skips_post(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.write_text("=== Compact Context Snapshot ===\n", encoding="utf-8")
    state = tmp_path / "state.json"
    set_bypass("compact-context-saver", ttl_seconds=120, state_path=state)
    result = _run(
        "post",
        env={
            "CLAUDE_COMPACT_CONTEXT": str(snapshot),
            "CLAUDE_BYPASS_STATE": str(state),
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_pre_handles_non_git_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = tmp_path / "snapshot"
    monkeypatch.chdir(tmp_path)
    result = _run("pre", env={"CLAUDE_COMPACT_CONTEXT": str(snapshot)})
    assert result.returncode == 0
    body = snapshot.read_text(encoding="utf-8")
    assert "Branch:" in body


def test_git_branch_falls_back_when_git_missing(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    bin_dir = tmp_path / "empty-bin"
    bin_dir.mkdir()
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
    assert result.returncode == 0
    body = snapshot.read_text(encoding="utf-8")
    assert "Branch: unknown" in body
    assert "not a git repo" in body


def test_git_status_non_zero_returncode(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    fake_git = bin_dir / "git"
    fake_git.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    fake_git.chmod(0o755)
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
    assert result.returncode == 0
    body = snapshot.read_text(encoding="utf-8")
    assert "not a git repo" in body
