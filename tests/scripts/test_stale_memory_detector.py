from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from _helpers.cov_env import apply_coverage_env

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "stale-memory-detector.py"
DAY = 86400


@pytest.fixture
def detector() -> ModuleType:
    spec = importlib.util.spec_from_file_location("stale_memory_detector", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _memory(root: Path, project: str, name: str, text: str) -> Path:
    path = root / project / "memory" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_find_memory_dirs_skips_projects_without_memory(detector, tmp_path):
    # Arrange
    _memory(tmp_path, "a", "x.md", "one\ntwo\n")
    (tmp_path / "b").mkdir()

    # Act
    result = detector.find_memory_dirs(tmp_path)

    # Assert
    assert result == [tmp_path / "a" / "memory"]


def test_a_stale_stub_with_a_dead_reference_gets_every_warning(detector, tmp_path):
    # Arrange
    path = _memory(tmp_path, "a", "x.md", "---\nSee `/nowhere/at/all.py`\n")
    now = path.stat().st_mtime + 200 * DAY

    # Act
    result = detector.check_memory_file(path, now)

    # Assert
    assert result == [
        f"{path}: references non-existent file: /nowhere/at/all.py",
        f"{path}: last modified 200 days ago, consider reviewing for staleness",
        f"{path}: nearly empty, may be a stub or failed write",
    ]


def test_main_prints_warnings_and_succeeds(detector, tmp_path, capsys):
    # Arrange
    path = _memory(tmp_path, "a", "x.md", "stub\n")
    _memory(tmp_path, "a", "MEMORY.md", "index\n")

    # Act
    code = detector.main(tmp_path, path.stat().st_mtime)

    # Assert
    assert code == 0
    assert capsys.readouterr().out == (
        "Scanned 1 memory files across 1 project(s).\n\n1 potential issues:\n"
        f"  WARN: {path}: nearly empty, may be a stub or failed write\n\n"
        "Review warnings above. No automatic changes were made.\n"
    )


def test_main_reports_healthy_files(detector, tmp_path, capsys):
    # Arrange
    path = _memory(tmp_path, "a", "x.md", "first fact\nsecond fact\n")

    # Act
    code = detector.main(tmp_path, path.stat().st_mtime)

    # Assert
    assert (code, capsys.readouterr().out.splitlines()[-1]) == (
        0,
        "All memory files look healthy.",
    )


def test_main_without_memory_dirs_says_so(detector, tmp_path, capsys):
    # Arrange
    missing = tmp_path / "none"

    # Act
    code = detector.main(missing)

    # Assert
    assert (code, capsys.readouterr().out) == (0, "No memory directories found.\n")


def test_the_script_runs_against_a_home_directory(tmp_path):
    # Arrange
    _memory(tmp_path / ".claude" / "projects", "p", "x.md", "first\nsecond\n")
    env = apply_coverage_env({**os.environ, "HOME": str(tmp_path)})

    # Act
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )

    # Assert
    assert (proc.returncode, proc.stdout.splitlines()[-1]) == (
        0,
        "All memory files look healthy.",
    )
