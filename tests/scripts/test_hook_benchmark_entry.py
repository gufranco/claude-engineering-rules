from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from _helpers.cov_env import apply_coverage_env

SCRIPT = (
    Path(__file__).resolve().parents[2] / ".github" / "scripts" / "hook-benchmark.py"
)


@pytest.fixture
def bench() -> ModuleType:
    spec = importlib.util.spec_from_file_location("hook_benchmark_entry", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("argv", "expected"),
    [([], "500"), (["--threshold", "250"], "250"), (["--threshold"], None)],
)
def test_threshold_from_reads_the_flag(bench, argv, expected):
    # Arrange
    args = argv

    # Act
    result = bench.threshold_from(args)

    # Assert
    assert result == expected


def test_a_threshold_flag_without_a_value_is_rejected(bench, capsys):
    # Arrange
    argv = ["--threshold"]

    # Act
    code = bench.main(argv)

    # Assert
    assert (code, capsys.readouterr().err) == (
        2,
        "--threshold needs a value in milliseconds\n",
    )


def test_a_threshold_no_hook_can_meet_fails_the_benchmark():
    # Arrange
    env = apply_coverage_env(dict(os.environ))

    # Act
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--threshold", "0"],
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
        check=False,
    )

    # Assert
    assert proc.returncode == 1
    assert "ms over 0 ms" in proc.stdout + proc.stderr
