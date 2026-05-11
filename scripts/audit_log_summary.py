#!/usr/bin/env python3
"""Daily audit-log summary generator.

Plan item 269. Reads the most recent records of `~/.claude/logs/hooks.log`
and emits a Markdown digest covering:

  - top 5 detectors fired
  - top 5 detectors suppressed
  - top 5 files with findings
  - p50 / p95 / p99 hook latency

Default window is the last 24 hours. The window is bounded by the
`--window` flag (e.g. `--window 1h`, `--window 7d`). Output goes to
stdout so the user can pipe to mail or save:

    python3 scripts/audit_log_summary.py --window 24h | mail -s "hook digest" $USER

Records older than the window are skipped silently. Malformed lines are
also skipped without raising. The script never modifies the audit log.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from collections import Counter
from typing import Any

DEFAULT_LOG_PATH = os.path.expanduser("~/.claude/logs/hooks.log")
DEFAULT_BACKUP_PATH = DEFAULT_LOG_PATH + ".1"
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

_WINDOW_RE = re.compile(r"^(?P<n>\d+)(?P<unit>[smhd])$")
_UNIT_TO_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_window(spec: str) -> int:
    m = _WINDOW_RE.match(spec)
    if not m:
        raise ValueError(f"invalid window spec: {spec!r} (use e.g. 24h, 7d)")
    return int(m.group("n")) * _UNIT_TO_SECONDS[m.group("unit")]


def _record_ts(rec: dict[str, Any]) -> float | None:
    raw = rec.get("ts") or rec.get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        return time.mktime(time.strptime(raw, TS_FORMAT))
    except (ValueError, OverflowError):
        return None


def _read_records(paths: list[str], cutoff: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in paths:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    rec = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict):
                    continue
                ts = _record_ts(rec)
                if ts is None or ts < cutoff:
                    continue
                out.append(rec)
    return out


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    idx = max(0, int(len(sorted_values) * pct) - 1)
    return sorted_values[idx]


def _expand_detector_tags(rec: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("detector", "detector_tag"):
        raw = rec.get(key)
        if isinstance(raw, str) and raw:
            for piece in raw.split(","):
                head = piece.split(":", 1)[0].strip()
                if head:
                    out.append(head)
    return out


def render_markdown(records: list[dict[str, Any]], hook_filter: str | None) -> str:
    if hook_filter:
        records = [r for r in records if r.get("hook") == hook_filter]

    blocks = [
        r for r in records if (r.get("decision_class") or r.get("decision")) == "block"
    ]
    suppresses = [r for r in records if r.get("suppressed") is True]

    detector_counter: Counter[str] = Counter()
    for r in blocks:
        for tag in _expand_detector_tags(r):
            detector_counter[tag] += 1

    suppress_counter: Counter[str] = Counter()
    for r in suppresses:
        for tag in _expand_detector_tags(r):
            suppress_counter[tag] += 1

    file_counter: Counter[str] = Counter()
    for r in blocks:
        fp = r.get("file_path") or r.get("file")
        if isinstance(fp, str) and fp:
            file_counter[fp] += 1

    latencies = [
        float(r["latency_ms"])
        for r in records
        if isinstance(r.get("latency_ms"), (int, float))
    ]

    parts: list[str] = []
    parts.append("# Hook activity digest")
    parts.append("")
    parts.append(f"- Records analyzed: {len(records)}")
    parts.append(f"- Block decisions: {len(blocks)}")
    parts.append(f"- Suppressed findings: {len(suppresses)}")
    if latencies:
        parts.append(
            f"- Latency: p50={statistics.median(latencies):.2f}ms "
            f"p95={_percentile(latencies, 0.95):.2f}ms "
            f"p99={_percentile(latencies, 0.99):.2f}ms"
        )
    parts.append("")
    parts.append("## Top detectors fired")
    if detector_counter:
        for tag, count in detector_counter.most_common(5):
            parts.append(f"- {tag}: {count}")
    else:
        parts.append("- (no blocks recorded in window)")
    parts.append("")
    parts.append("## Top detectors suppressed")
    if suppress_counter:
        for tag, count in suppress_counter.most_common(5):
            parts.append(f"- {tag}: {count}")
    else:
        parts.append("- (no suppressions recorded in window)")
    parts.append("")
    parts.append("## Top files with findings")
    if file_counter:
        for fp, count in file_counter.most_common(5):
            parts.append(f"- {fp}: {count}")
    else:
        parts.append("- (no file paths recorded)")
    parts.append("")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily audit-log summary")
    parser.add_argument("--window", default="24h", help="lookback window, e.g. 24h, 7d")
    parser.add_argument("--log-path", default=DEFAULT_LOG_PATH)
    parser.add_argument("--backup-path", default=DEFAULT_BACKUP_PATH)
    parser.add_argument(
        "--hook",
        default=None,
        help="filter to one hook name (e.g. mutation-method-blocker)",
    )
    args = parser.parse_args()
    seconds = parse_window(args.window)
    cutoff = time.time() - seconds
    records = _read_records([args.backup_path, args.log_path], cutoff)
    sys.stdout.write(render_markdown(records, args.hook))
    return 0


if __name__ == "__main__":
    sys.exit(main())
