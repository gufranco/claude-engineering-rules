"""Tests for `hooks/english-only-reminder.py`.


Observable behavior: emit a `<system-reminder>` block locking the assistant
to English on stdout, exit 0. Bypass via env or file registry suppresses
the reminder.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "english-only-reminder.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402

_TESTS_DIR = ROOT / "tests"
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _helpers.cov_env import apply_coverage_env  # noqa: E402


def _run(env: dict | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input="",
        capture_output=True,
        text=True,
        env=apply_coverage_env(merged),
        timeout=5,
    )


def test_emits_system_reminder_block() -> None:
    # Arrange
    # Act
    result = _run()
    # Assert
    assert result.returncode == 0
    assert "<system-reminder>" in result.stdout
    assert "</system-reminder>" in result.stdout
    assert "LANGUAGE LOCK" in result.stdout
    assert "Respond in English" in result.stdout


def test_emits_no_stderr() -> None:
    # Arrange
    # Act
    result = _run()
    # Assert
    assert result.stderr == ""


def test_env_disable_suppresses_reminder() -> None:
    # Arrange
    # Act
    result = _run({"ENGLISH_REMINDER_DISABLE": "1"})
    # Assert
    assert result.returncode == 0
    assert result.stdout == ""


def test_file_bypass_suppresses_reminder(tmp_path: Path) -> None:
    # Arrange
    state = tmp_path / "state.json"
    set_bypass("english-only-reminder", ttl_seconds=120, state_path=state)
    # Act
    result = _run({"CLAUDE_BYPASS_STATE": str(state)})
    # Assert
    assert result.returncode == 0
    assert result.stdout == ""


def test_expired_file_entry_does_not_bypass(tmp_path: Path) -> None:
    # Arrange
    state = tmp_path / "state.json"
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    state.write_text(
        json.dumps(
            {
                "version": 1,
                "bypasses": [{"hook": "english-only-reminder", "expires_at": past}],
            }
        ),
        encoding="utf-8",
    )
    # Act
    result = _run({"CLAUDE_BYPASS_STATE": str(state)})
    # Assert
    assert "LANGUAGE LOCK" in result.stdout
