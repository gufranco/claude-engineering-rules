from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from _helpers.cov_env import apply_coverage_env

HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks"
HOOKS = sorted(HOOKS_DIR.glob("*.py"))
ISOLATION = {"CLAUDE_BYPASS_STATE": os.devnull, "CLAUDE_HOOK_AUDIT_DISABLE": "1"}


@pytest.mark.parametrize("hook", HOOKS, ids=[path.name for path in HOOKS])
@pytest.mark.parametrize("stdin", ["not json", "[1, 2]"], ids=["garbage", "list"])
def test_malformed_input_never_crashes_a_hook(hook, stdin, tmp_path):
    # Arrange
    env = apply_coverage_env(
        {**os.environ, **ISOLATION, "HOME": str(tmp_path), "SHELL": "/bin/zsh"}
    )

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
        timeout=60,
        check=False,
    )

    # Assert
    assert proc.returncode in (0, 2)
    assert "Traceback" not in proc.stderr
