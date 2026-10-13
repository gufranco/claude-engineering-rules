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


@pytest.fixture
def hooks_dir(tmp_path: Path) -> Path:
    target = tmp_path / "hooks"
    target.mkdir()
    _hook(target, "fast", "import sys\nsys.exit(0)\n")
    _hook(target, "unregistered", "import sys\nsys.exit(1)\n")
    return target


def test_registered_hooks_under_the_threshold_pass(hooks_dir, tmp_path):
    # Arrange
    settings = _settings(tmp_path / "settings.json", ["fast"])

    # Act
    proc = _bench(hooks_dir, settings, 5000)

    # Assert
    assert (proc.returncode, "unregistered" in proc.stdout) == (0, False)


@pytest.mark.parametrize(
    ("hooks", "source", "reason"),
    [
        (["slow"], "import time, sys\ntime.sleep(0.4)\nsys.exit(0)\n", "over 100 ms"),
        (["crash"], "import sys\nsys.exit(1)\n", "exited 1"),
        (["absent"], None, "missing"),
    ],
)
def test_a_slow_crashing_or_missing_hook_fails_the_gate(
    hooks_dir, tmp_path, hooks, source, reason
):
    # Arrange
    if source is not None:
        _hook(hooks_dir, hooks[0], source)
    settings = _settings(tmp_path / "settings.json", hooks)

    # Act
    proc = _bench(hooks_dir, settings, 100)

    # Assert
    assert (proc.returncode, reason in proc.stderr) == (1, True)
