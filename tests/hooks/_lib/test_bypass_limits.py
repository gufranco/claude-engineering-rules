from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.bypass_writer import set_bypass  # noqa: E402

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


def _registry(tmp_path: Path, hook: str, seconds_ahead: int) -> Path:
    path = tmp_path / "bypass.json"
    expires = (NOW + timedelta(seconds=seconds_ahead)).isoformat()
    path.write_text(
        json.dumps({"version": 1, "bypasses": [{"hook": hook, "expires_at": expires}]}),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("hook", "seconds_ahead"),
    [
        ("secret-scanner", 3600 * 24 * 365),
        ("secret-scanner", 3600 + 120),
        ("*", 1200 + 120),
    ],
)
def test_an_entry_beyond_its_ttl_ceiling_is_ignored(tmp_path, hook, seconds_ahead):
    # Arrange
    path = _registry(tmp_path, hook, seconds_ahead)

    # Act
    result = is_bypassed("secret-scanner", state_path=path, now=NOW)

    # Assert
    assert result is False


@pytest.mark.parametrize(
    ("hook", "seconds_ahead"), [("secret-scanner", 3600), ("*", 1200)]
)
def test_an_entry_within_its_ceiling_is_honored(tmp_path, hook, seconds_ahead):
    # Arrange
    path = _registry(tmp_path, hook, seconds_ahead)

    # Act
    result = is_bypassed("secret-scanner", state_path=path, now=NOW)

    # Assert
    assert result is True


def test_a_wildcard_set_without_a_ttl_lasts_five_minutes(tmp_path):
    # Arrange
    path = tmp_path / "bypass.json"

    # Act
    set_bypass("*", state_path=path, now=NOW)

    # Assert
    entry = json.loads(path.read_text(encoding="utf-8"))["bypasses"][0]
    assert entry["expires_at"] == (NOW + timedelta(seconds=300)).isoformat()


def test_the_cli_reports_the_ttl_it_applied(tmp_path):
    # Arrange
    state = tmp_path / "bypass.json"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "bypass.py"),
        "set",
        "x",
        "--ttl",
        "99999",
    ]

    # Act
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env={
            "CLAUDE_BYPASS_STATE": str(state),
            "HOME": str(tmp_path),
            "PATH": "/usr/bin:/bin",
        },
        check=False,
        timeout=30,
    )

    # Assert
    assert (proc.returncode, "ttl=3600s" in proc.stdout) == (0, True)
