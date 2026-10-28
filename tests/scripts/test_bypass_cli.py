from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from _helpers.cov_env import apply_coverage_env

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "bypass.py"


def _run(state: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = apply_coverage_env({**os.environ, "CLAUDE_BYPASS_STATE": str(state)})
    env = {**env, "CLAUDE_BYPASS_STATE": str(state)}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )


def test_list_shows_an_engaged_entry(tmp_path):
    # Arrange
    state = tmp_path / "bypass.json"
    _run(state, "set", "comment-blocker", "--ttl", "120", "--reason", "fixture")

    # Act
    proc = _run(state, "list")

    # Assert
    assert proc.stdout.startswith("hook='comment-blocker' expires_at=")
    assert proc.stdout.rstrip().endswith("reason='fixture'")


def test_clear_removes_the_named_entry(tmp_path):
    # Arrange
    state = tmp_path / "bypass.json"
    _run(state, "set", "comment-blocker")

    # Act
    proc = _run(state, "clear", "comment-blocker")

    # Assert
    assert proc.stdout == "bypass cleared: hook='comment-blocker' removed=1\n"


def test_set_reports_the_applied_ttl(tmp_path):
    # Arrange
    state = tmp_path / "bypass.json"

    # Act
    proc = _run(state, "set", "tdd-gate")

    # Assert
    assert proc.stdout.startswith("bypass engaged: hook='tdd-gate' ttl=")


def test_clear_without_a_hook_clears_everything(tmp_path):
    # Arrange
    state = tmp_path / "bypass.json"
    _run(state, "set", "a")

    # Act
    proc = _run(state, "clear")

    # Assert
    assert proc.stdout == "bypass cleared: hook='*all*' removed=1\n"


def test_list_without_a_registry_says_so(tmp_path):
    # Arrange
    state = tmp_path / "missing.json"

    # Act
    proc = _run(state, "list")

    # Assert
    assert proc.stdout == "no bypass registry (file does not exist)\n"


@pytest.mark.parametrize("payload", [{"bypasses": []}, ["not", "a", "mapping"]])
def test_list_with_no_entries_says_so(tmp_path, payload):
    # Arrange
    state = tmp_path / "bypass.json"
    state.write_text(json.dumps(payload), encoding="utf-8")

    # Act
    proc = _run(state, "list")

    # Assert
    assert proc.stdout == "no active bypasses\n"


def test_list_skips_malformed_entries_and_defaults_missing_fields(tmp_path):
    # Arrange
    state = tmp_path / "bypass.json"
    state.write_text(json.dumps({"bypasses": ["junk", {}]}), encoding="utf-8")

    # Act
    proc = _run(state, "list")

    # Assert
    assert proc.stdout == "hook='?' expires_at=?\n"


def test_list_fails_on_an_unreadable_registry(tmp_path):
    # Arrange
    state = tmp_path / "bypass.json"
    state.write_text("{broken", encoding="utf-8")

    # Act
    proc = _run(state, "list")

    # Assert
    assert proc.returncode == 1
    assert proc.stderr.startswith("cannot read registry: ")
