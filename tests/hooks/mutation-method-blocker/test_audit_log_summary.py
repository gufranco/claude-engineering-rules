"""Audit log summary tests.

Plan item 269. Verifies `scripts/audit_log_summary.py`:

  - Renders top detectors / suppressions / files with a stable header.
  - Reports p50/p95/p99 latency when latency fields are present.
  - Filters by hook name when --hook is supplied.
  - Skips records older than the requested window.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import audit_log_summary  # noqa: E402

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _ts(seconds_ago: int) -> str:
    return time.strftime(TS_FORMAT, time.gmtime(time.time() - seconds_ago))


def _write(path: Path, records: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n",
        encoding="utf-8",
    )


def test_parse_window_units() -> None:
    assert audit_log_summary.parse_window("60s") == 60
    assert audit_log_summary.parse_window("5m") == 300
    assert audit_log_summary.parse_window("2h") == 7200
    assert audit_log_summary.parse_window("3d") == 259200


def test_parse_window_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        audit_log_summary.parse_window("forever")


def test_render_markdown_has_headers_and_top_detectors(tmp_path: Path) -> None:
    log = tmp_path / "hooks.log"
    _write(
        log,
        [
            {
                "ts": _ts(60),
                "hook": "mutation-method-blocker",
                "decision_class": "block",
                "detector": "array.push",
                "latency_ms": 30.0,
                "file_path": "src/a.ts",
            },
            {
                "ts": _ts(60),
                "hook": "mutation-method-blocker",
                "decision_class": "block",
                "detector": "array.push",
                "latency_ms": 80.0,
                "file_path": "src/a.ts",
            },
            {
                "ts": _ts(60),
                "hook": "mutation-method-blocker",
                "decision_class": "block",
                "detector": "object.assign",
                "latency_ms": 50.0,
                "file_path": "src/b.ts",
            },
        ],
    )
    cutoff = time.time() - 86400
    records = audit_log_summary._read_records([str(log)], cutoff)
    md = audit_log_summary.render_markdown(records, hook_filter=None)
    assert "# Hook activity digest" in md
    assert "Top detectors fired" in md
    assert "array.push: 2" in md
    assert "object.assign: 1" in md
    assert "src/a.ts: 2" in md
    assert "p50=" in md and "p95=" in md and "p99=" in md


def test_hook_filter_drops_other_hooks(tmp_path: Path) -> None:
    log = tmp_path / "hooks.log"
    _write(
        log,
        [
            {
                "ts": _ts(30),
                "hook": "mutation-method-blocker",
                "decision_class": "block",
                "detector": "array.push",
            },
            {
                "ts": _ts(30),
                "hook": "as-any-blocker",
                "decision_class": "block",
                "detector": "as-any",
            },
        ],
    )
    cutoff = time.time() - 3600
    records = audit_log_summary._read_records([str(log)], cutoff)
    md = audit_log_summary.render_markdown(
        records, hook_filter="mutation-method-blocker"
    )
    assert "array.push" in md
    assert "as-any" not in md


def test_old_records_excluded_by_window(tmp_path: Path) -> None:
    log = tmp_path / "hooks.log"
    _write(
        log,
        [
            {
                "ts": _ts(40 * 86400),
                "hook": "mutation-method-blocker",
                "decision_class": "block",
                "detector": "array.push",
            }
        ],
    )
    cutoff = time.time() - 24 * 3600
    records = audit_log_summary._read_records([str(log)], cutoff)
    md = audit_log_summary.render_markdown(records, hook_filter=None)
    assert "array.push" not in md
    assert "Records analyzed: 0" in md


def test_suppressed_records_aggregated(tmp_path: Path) -> None:
    log = tmp_path / "hooks.log"
    _write(
        log,
        [
            {
                "ts": _ts(60),
                "hook": "mutation-method-blocker",
                "decision_class": "allow",
                "suppressed": True,
                "detector": "array.push",
            },
            {
                "ts": _ts(60),
                "hook": "mutation-method-blocker",
                "decision_class": "allow",
                "suppressed": True,
                "detector": "array.push",
            },
        ],
    )
    cutoff = time.time() - 3600
    records = audit_log_summary._read_records([str(log)], cutoff)
    md = audit_log_summary.render_markdown(records, hook_filter=None)
    assert "Suppressed findings: 2" in md
    assert "array.push: 2" in md
