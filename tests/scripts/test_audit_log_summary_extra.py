"""Extra coverage for `scripts/audit_log_summary.py`.

Targets ts validation, malformed input handling, percentile edge cases,
and the CLI entry point branches.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import audit_log_summary as als  # noqa: E402

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _ts(seconds_ago: int) -> str:
    return time.strftime(TS_FORMAT, time.gmtime(time.time() - seconds_ago))


# --------------------------------------------------------------------------- #
# _record_ts edge cases
# --------------------------------------------------------------------------- #


def test_record_ts_returns_none_when_missing() -> None:
    assert als._record_ts({}) is None


def test_record_ts_returns_none_when_non_string() -> None:
    assert als._record_ts({"ts": 12345}) is None


def test_record_ts_returns_none_for_invalid_format() -> None:
    assert als._record_ts({"ts": "not-a-date"}) is None


def test_record_ts_handles_overflow() -> None:
    # Arrange: a date so far in the future it overflows mktime on some platforms
    # but at minimum it parses; test the explicit fallback path.
    assert als._record_ts({"ts": "9999-99-99T99:99:99Z"}) is None


# --------------------------------------------------------------------------- #
# _read_records edge cases
# --------------------------------------------------------------------------- #


def test_read_records_skips_missing_paths(tmp_path: Path) -> None:
    # Arrange
    missing = tmp_path / "absent.log"
    cutoff = time.time() - 86400

    # Act
    records = als._read_records([str(missing)], cutoff)

    # Assert
    assert records == []


def test_read_records_skips_blank_and_malformed(tmp_path: Path) -> None:
    # Arrange
    log = tmp_path / "log"
    log.write_text(
        "\n"
        "not json\n"
        "[1,2,3]\n"
        + json.dumps({"ts": _ts(60), "hook": "h", "decision_class": "block"})
        + "\n",
        encoding="utf-8",
    )
    cutoff = time.time() - 86400

    # Act
    records = als._read_records([str(log)], cutoff)

    # Assert
    assert len(records) == 1
    assert records[0]["hook"] == "h"


# --------------------------------------------------------------------------- #
# _percentile edge cases
# --------------------------------------------------------------------------- #


def test_percentile_returns_zero_for_empty() -> None:
    assert als._percentile([], 0.95) == 0.0


def test_percentile_returns_single_value() -> None:
    assert als._percentile([42.0], 0.95) == 42.0


# --------------------------------------------------------------------------- #
# main / CLI
# --------------------------------------------------------------------------- #


def test_main_writes_markdown_to_stdout(tmp_path: Path, monkeypatch, capsys) -> None:
    # Arrange
    log = tmp_path / "hooks.log"
    log.write_text(
        json.dumps(
            {
                "ts": _ts(60),
                "hook": "mutation-method-blocker",
                "decision_class": "block",
                "detector": "array.push",
                "latency_ms": 12.0,
                "file_path": "src/a.ts",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_log_summary",
            "--window",
            "24h",
            "--log-path",
            str(log),
            "--backup-path",
            str(tmp_path / "backup-missing.log"),
        ],
    )

    # Act
    rc = als.main()
    captured = capsys.readouterr()

    # Assert
    assert rc == 0
    assert "Hook activity digest" in captured.out
    assert "array.push" in captured.out


def test_main_module_entry_runs_as_subprocess(tmp_path: Path) -> None:
    # Arrange
    script = SCRIPTS_DIR / "audit_log_summary.py"
    log = tmp_path / "hooks.log"
    log.write_text("", encoding="utf-8")

    # Act
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--window",
            "1h",
            "--log-path",
            str(log),
            "--backup-path",
            str(tmp_path / "missing.log"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    # Assert
    assert proc.returncode == 0
    assert "Hook activity digest" in proc.stdout
