"""Tests for `hooks/smart-formatter.py`.


Observable behavior: append the edited file path to the per-session batch
file. Ignore paths under cache/node_modules/.git/dist/build. Ignore missing
files. Honor `hook_profile.should_run`. Bypass via env or file registry.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "smart-formatter.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402

_TESTS_DIR = ROOT / "tests"
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _helpers.cov_env import apply_coverage_env  # noqa: E402


def _run(file_path: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": file_path}})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env=apply_coverage_env(merged),
        timeout=5,
    )


def _env(batch: Path) -> dict:
    return {"CLAUDE_FORMATTER_BATCH": str(batch)}


def test_appends_existing_file_to_batch(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "x.ts"
    target.write_text("export const a = 1;\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    # Act
    result = _run(str(target), env=_env(batch))
    # Assert
    assert result.returncode == 0
    assert batch.read_text(encoding="utf-8").strip() == str(target)


def test_appends_multiple_invocations(tmp_path: Path) -> None:
    # Arrange
    a = tmp_path / "a.ts"
    a.write_text("//\n", encoding="utf-8")
    b = tmp_path / "b.ts"
    b.write_text("//\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    # Act
    _run(str(a), env=_env(batch))
    _run(str(b), env=_env(batch))
    # Assert
    lines = batch.read_text(encoding="utf-8").splitlines()
    assert lines == [str(a), str(b)]


def test_ignores_missing_file(tmp_path: Path) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"
    # Act
    result = _run(str(tmp_path / "nope.ts"), env=_env(batch))
    # Assert
    assert result.returncode == 0
    assert not batch.exists()


def test_ignores_empty_path(tmp_path: Path) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"
    # Act
    result = _run("", env=_env(batch))
    # Assert
    assert result.returncode == 0
    assert not batch.exists()


@pytest.mark.parametrize(
    "fragment",
    [
        "node_modules/foo.ts",
        ".git/HEAD.ts",
        "dist/main.ts",
        "build/main.ts",
        ".claude/cache/x.ts",
    ],
)
def test_skips_excluded_paths(tmp_path: Path, fragment: str) -> None:
    # Arrange
    target = tmp_path / fragment
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("//\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    # Act
    result = _run(str(target), env=_env(batch))
    # Assert
    assert result.returncode == 0
    assert not batch.exists()


def test_handles_malformed_json(tmp_path: Path) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"
    # Act
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json",
        capture_output=True,
        text=True,
        env=apply_coverage_env({**os.environ, **_env(batch)}),
        timeout=5,
    )
    # Assert
    assert result.returncode == 0


def test_env_disable_short_circuits(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "x.ts"
    target.write_text("//\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    # Act
    result = _run(str(target), env={**_env(batch), "SMART_FORMATTER_DISABLE": "1"})
    # Assert
    assert result.returncode == 0
    assert not batch.exists()


def test_file_bypass_short_circuits(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "x.ts"
    target.write_text("//\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    state = tmp_path / "state.json"
    set_bypass("smart-formatter", ttl_seconds=120, state_path=state)
    # Act
    result = _run(str(target), env={**_env(batch), "CLAUDE_BYPASS_STATE": str(state)})
    # Assert
    assert result.returncode == 0
    assert not batch.exists()


def test_handles_non_dict_root(tmp_path: Path) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"
    # Act
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="[1,2,3]",
        capture_output=True,
        text=True,
        env=apply_coverage_env({**os.environ, **_env(batch)}),
        timeout=5,
    )
    # Assert
    assert result.returncode == 0
    assert not batch.exists()


def test_handles_non_dict_tool_input(tmp_path: Path) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"
    # Act
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input='{"tool_input": "scalar"}',
        capture_output=True,
        text=True,
        env=apply_coverage_env({**os.environ, **_env(batch)}),
        timeout=5,
    )
    # Assert
    assert result.returncode == 0
    assert not batch.exists()


def test_handles_non_string_file_path(tmp_path: Path) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"
    # Act
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input='{"tool_input": {"file_path": 42}}',
        capture_output=True,
        text=True,
        env=apply_coverage_env({**os.environ, **_env(batch)}),
        timeout=5,
    )
    # Assert
    assert result.returncode == 0
    assert not batch.exists()


def test_profile_disable_short_circuits(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "x.ts"
    target.write_text("//\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    # Act
    result = _run(
        str(target),
        env={**_env(batch), "CLAUDE_DISABLED_HOOKS": "smart-formatter"},
    )
    # Assert
    assert result.returncode == 0
    assert not batch.exists()
