from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "hooks" / "_lib" / "bench_hooks.py"


def _hook(directory: Path, name: str, body: str) -> None:
    (directory / f"{name}.py").write_text(
        textwrap.dedent(body).lstrip(), encoding="utf-8"
    )


def _settings(path: Path, names: list[str]) -> Path:
    entries = [
        {"hooks": [{"type": "command", "command": f"python3 ~/.claude/hooks/{n}.py"}]}
        for n in names
    ]
    path.write_text(json.dumps({"hooks": {"PreToolUse": entries}}), encoding="utf-8")
    return path


def _bench(
    hooks_dir: Path, settings: Path, threshold_ms: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--hooks-dir",
            str(hooks_dir),
            "--settings",
            str(settings),
            "--iterations",
            "1",
            "--warmup",
            "0",
            "--threshold-ms",
            str(threshold_ms),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


PASSING_THRESHOLD_MS = 600_000
TIGHT_THRESHOLD_MS = 100


@pytest.fixture
def hooks_dir(tmp_path: Path) -> Path:
    target = tmp_path / "hooks"
    target.mkdir()
    _hook(target, "fast", "import sys\nsys.exit(0)\n")
    _hook(target, "unregistered", "import sys\nsys.exit(1)\n")
    return target


def _row_names(stdout: str) -> list[str]:
    return [line.split()[0] for line in stdout.splitlines()[2:]]


def test_registered_hooks_under_the_threshold_pass(
    hooks_dir: Path, tmp_path: Path
) -> None:
    # Arrange
    settings = _settings(tmp_path / "settings.json", ["fast"])

    # Act
    proc = _bench(hooks_dir, settings, PASSING_THRESHOLD_MS)

    # Assert
    assert (proc.returncode, _row_names(proc.stdout), proc.stderr) == (0, ["fast"], "")


def test_a_hook_whose_p50_exceeds_the_threshold_fails_the_gate(
    hooks_dir: Path, tmp_path: Path
) -> None:
    # Arrange
    _hook(hooks_dir, "slow", "import time, sys\ntime.sleep(0.4)\nsys.exit(0)\n")
    settings = _settings(tmp_path / "settings.json", ["slow"])

    # Act
    proc = _bench(hooks_dir, settings, TIGHT_THRESHOLD_MS)

    # Assert
    lines = proc.stderr.splitlines()
    assert proc.returncode == 1
    assert len(lines) == 1
    assert lines[0].startswith("FAIL slow: p50 ") is True
    assert lines[0].endswith(" ms over 100 ms") is True


def test_a_crashing_hook_fails_the_gate(hooks_dir: Path, tmp_path: Path) -> None:
    # Arrange
    _hook(hooks_dir, "crash", "import sys\nsys.exit(1)\n")
    settings = _settings(tmp_path / "settings.json", ["crash"])

    # Act
    proc = _bench(hooks_dir, settings, PASSING_THRESHOLD_MS)

    # Assert
    assert (proc.returncode, proc.stderr) == (1, "FAIL crash: exited 1\n")


def test_a_registered_hook_missing_from_disk_fails_the_gate(
    hooks_dir: Path, tmp_path: Path
) -> None:
    # Arrange
    settings = _settings(tmp_path / "settings.json", ["absent"])

    # Act
    proc = _bench(hooks_dir, settings, PASSING_THRESHOLD_MS)

    # Assert
    assert (proc.returncode, proc.stderr) == (1, "FAIL absent: missing\n")
