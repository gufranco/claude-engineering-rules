"""Smoke test: file-bypass short-circuits every Python hook.

Engages the file registry for each hook and runs it with an empty
PreToolUse payload. The hook must exit 0 without producing block output.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = ROOT / "hooks"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402

_TESTS_DIR = ROOT / "tests"
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _helpers.cov_env import apply_coverage_env  # noqa: E402

# Hooks that read no stdin or never short-circuit on bypass alone (e.g. they
# need the profile gate first). Skip-list keeps the smoke tests focused on the
# common case where bypass alone is sufficient.
SKIP = {"mutation-method-blocker.py"}


def _hooks() -> list[Path]:
    return sorted(p for p in HOOKS_DIR.glob("*.py") if p.name not in SKIP)


@pytest.mark.parametrize("hook_path", _hooks(), ids=lambda p: p.stem)
def test_file_bypass_short_circuits_hook(hook_path: Path, tmp_path: Path) -> None:
    # Arrange
    state = tmp_path / ".bypass-state.json"
    set_bypass(hook_path.stem, ttl_seconds=120, state_path=state)
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo noop"}})
    env = apply_coverage_env({**os.environ, "CLAUDE_BYPASS_STATE": str(state)})
    # Act
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=5,
    )
    # Assert
    assert result.returncode == 0, (
        f"{hook_path.name} expected exit 0 with bypass active; got "
        f"{result.returncode}; stderr={result.stderr[:200]}"
    )
