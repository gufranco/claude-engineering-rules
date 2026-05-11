"""Extra coverage for `scripts/audit_log_compact.py`.

Targets branches not exercised by `tests/hooks/.../test_audit_log_compact.py`:
ts validation, malformed records, single-latency p95, OS errors on rewrite,
and the CLI entry point.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import audit_log_compact as compact_module  # noqa: E402

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _ts(seconds_ago: int) -> str:
    return time.strftime(TS_FORMAT, time.gmtime(time.time() - seconds_ago))


# --------------------------------------------------------------------------- #
# _parse_ts
# --------------------------------------------------------------------------- #


def test_parse_ts_returns_none_for_missing() -> None:
    assert compact_module._parse_ts({}) is None


def test_parse_ts_returns_none_for_non_string() -> None:
    assert compact_module._parse_ts({"ts": 123}) is None


def test_parse_ts_returns_none_for_invalid_format() -> None:
    assert compact_module._parse_ts({"ts": "not-a-date"}) is None


def test_parse_ts_accepts_alias_field() -> None:
    raw = "2026-05-10T12:00:00Z"
    assert compact_module._parse_ts({"timestamp": raw}) is not None


# --------------------------------------------------------------------------- #
# _read_records
# --------------------------------------------------------------------------- #


def test_read_records_skips_blank_and_non_dict_lines(tmp_path: Path) -> None:
    # Arrange
    log = tmp_path / "log"
    log.write_text('\n\n[1,2,3]\n{"hook":"x"}\n', encoding="utf-8")

    # Act
    items = compact_module._read_records(str(log))

    # Assert
    assert len(items) == 1
    assert items[0][0]["hook"] == "x"


def test_read_records_handles_missing_file(tmp_path: Path) -> None:
    assert compact_module._read_records(str(tmp_path / "missing.log")) == []


# --------------------------------------------------------------------------- #
# _summary_for_bucket
# --------------------------------------------------------------------------- #


def test_summary_for_bucket_handles_no_latency() -> None:
    # Arrange
    records = [{"detector": "array.push"}]

    # Act
    summary = compact_module._summary_for_bucket(("2026-04-09", "h", "block"), records)

    # Assert
    assert "p50_latency" not in summary
    assert summary["count"] == 1


def test_summary_for_bucket_handles_single_latency() -> None:
    # Arrange
    records = [{"detector": "x", "latency_ms": 12.5}]

    # Act
    summary = compact_module._summary_for_bucket(("2026-04-09", "h", "block"), records)

    # Assert
    assert summary["p50_latency"] == 12.5
    assert summary["p95_latency"] == 12.5


def test_summary_for_bucket_aggregates_split_detectors() -> None:
    # Arrange
    records = [{"detector": "array.push,object.assign,array.push"}]

    # Act
    summary = compact_module._summary_for_bucket(("2026-01-01", "h", "block"), records)

    # Assert
    detector_names = [d[0] for d in summary["top_detectors"]]
    assert detector_names[0] == "array.push"


def test_summary_for_bucket_uses_detector_tag_alias() -> None:
    # Arrange
    records = [{"detector_tag": "object.assign"}]

    # Act
    summary = compact_module._summary_for_bucket(("2026-01-01", "h", "block"), records)

    # Assert
    assert summary["top_detectors"] == [("object.assign", 1)]


# --------------------------------------------------------------------------- #
# compact: OS errors on rewrite
# --------------------------------------------------------------------------- #


def test_compact_propagates_os_error_after_cleanup(tmp_path: Path) -> None:
    # Arrange
    log = tmp_path / "hooks.log"
    summary = tmp_path / "hooks.summary.jsonl"
    forty_days = 40 * 86400
    log.write_text(
        json.dumps(
            {
                "ts": _ts(forty_days),
                "hook": "h",
                "decision_class": "block",
                "latency_ms": 12.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # Patch os.replace to raise after the temp file is written.
    real_replace = compact_module.os.replace

    def fake_replace(*_args, **_kwargs):
        raise OSError("replace failed")

    # Act / Assert
    with patch.object(compact_module.os, "replace", side_effect=fake_replace):
        with pytest.raises(OSError, match="replace failed"):
            compact_module.compact(str(log), str(summary), retention_days=30)

    # Restore in case patch context fails to restore after exception.
    compact_module.os.replace = real_replace


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def test_main_dry_run_writes_counts(tmp_path: Path, monkeypatch, capsys) -> None:
    # Arrange
    log = tmp_path / "hooks.log"
    summary = tmp_path / "hooks.summary.jsonl"
    log.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_log_compact",
            "--log-path",
            str(log),
            "--summary-path",
            str(summary),
            "--dry-run",
        ],
    )

    # Act
    rc = compact_module.main()
    captured = capsys.readouterr()

    # Assert
    assert rc == 0
    parsed = json.loads(captured.out)
    assert parsed["kept"] == 0


def test_main_module_entry_runs_as_subprocess(tmp_path: Path) -> None:
    # Arrange
    script = SCRIPTS_DIR / "audit_log_compact.py"
    log = tmp_path / "hooks.log"
    summary = tmp_path / "summary.jsonl"
    log.write_text("", encoding="utf-8")

    # Act
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--log-path",
            str(log),
            "--summary-path",
            str(summary),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    # Assert
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert "kept" in payload
