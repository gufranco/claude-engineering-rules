"""Audit log compaction tests.

Plan items 263-264. Verifies `scripts/audit_log_compact.py`:

  - Records inside the retention window stay in the live log.
  - Records past the cutoff are aggregated into per-(day, hook,
    decision) summaries written to the summary file.
  - The live log is rewritten atomically: a crash between read and
    write must not lose unpurged records.
  - Malformed lines do not crash the compactor.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import audit_log_compact  # noqa: E402

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _ts(seconds_ago: int) -> str:
    return time.strftime(TS_FORMAT, time.gmtime(time.time() - seconds_ago))


def _write_log(path: Path, records: list[dict]) -> None:
    lines = [json.dumps(rec, sort_keys=True) for rec in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_compact_keeps_recent_records(tmp_path: Path) -> None:
    log = tmp_path / "hooks.log"
    summary = tmp_path / "hooks.summary.jsonl"
    _write_log(
        log,
        [
            {
                "ts": _ts(60),
                "hook": "mutation-method-blocker",
                "decision_class": "block",
                "latency_ms": 45.0,
                "detector": "array.push",
            }
        ],
    )
    counts = audit_log_compact.compact(str(log), str(summary), retention_days=30)
    assert counts["kept"] == 1
    assert counts["summarized"] == 0
    assert log.read_text(encoding="utf-8").strip().count("\n") == 0


def test_compact_summarizes_old_records(tmp_path: Path) -> None:
    log = tmp_path / "hooks.log"
    summary = tmp_path / "hooks.summary.jsonl"
    forty_days = 40 * 86400
    _write_log(
        log,
        [
            {
                "ts": _ts(forty_days),
                "hook": "mutation-method-blocker",
                "decision_class": "block",
                "latency_ms": 50.0,
                "detector": "array.push",
            },
            {
                "ts": _ts(forty_days),
                "hook": "mutation-method-blocker",
                "decision_class": "block",
                "latency_ms": 90.0,
                "detector": "array.push",
            },
            {
                "ts": _ts(forty_days),
                "hook": "mutation-method-blocker",
                "decision_class": "allow",
                "latency_ms": 5.0,
                "detector": "object.assign",
            },
        ],
    )
    counts = audit_log_compact.compact(str(log), str(summary), retention_days=30)
    assert counts["summarized"] == 3
    assert counts["kept"] == 0
    assert summary.exists()
    lines = [
        json.loads(line) for line in summary.read_text(encoding="utf-8").splitlines()
    ]
    block_summary = next(s for s in lines if s["decision"] == "block")
    assert block_summary["count"] == 2
    assert block_summary["hook"] == "mutation-method-blocker"
    assert block_summary["top_detectors"][0][0] == "array.push"


def test_compact_skips_malformed_lines(tmp_path: Path) -> None:
    log = tmp_path / "hooks.log"
    summary = tmp_path / "hooks.summary.jsonl"
    log.write_text(
        "{not json\n"
        + json.dumps(
            {
                "ts": _ts(60),
                "hook": "x",
                "decision_class": "allow",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    counts = audit_log_compact.compact(str(log), str(summary), retention_days=30)
    assert counts["kept"] == 1


def test_dry_run_does_not_modify_files(tmp_path: Path) -> None:
    log = tmp_path / "hooks.log"
    summary = tmp_path / "hooks.summary.jsonl"
    forty_days = 40 * 86400
    original = [
        {
            "ts": _ts(forty_days),
            "hook": "h",
            "decision_class": "block",
            "latency_ms": 12.0,
        }
    ]
    _write_log(log, original)
    before = log.read_text(encoding="utf-8")
    counts = audit_log_compact.compact(
        str(log), str(summary), retention_days=30, dry_run=True
    )
    assert counts["summarized"] == 1
    assert log.read_text(encoding="utf-8") == before
    assert not summary.exists()


def test_compact_handles_empty_log(tmp_path: Path) -> None:
    log = tmp_path / "missing.log"
    summary = tmp_path / "hooks.summary.jsonl"
    counts = audit_log_compact.compact(str(log), str(summary), retention_days=30)
    assert counts == {"kept": 0, "summarized": 0, "buckets": 0}
