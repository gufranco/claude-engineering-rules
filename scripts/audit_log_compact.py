#!/usr/bin/env python3
"""Audit log retention compaction.

Plan items 263-264 (D43). Reads `~/.claude/logs/hooks.log`, summarizes
records older than `--retention-days` (default 30), appends one summary
record per (hook, decision_class, day) to `~/.claude/logs/hooks.summary.jsonl`,
then rewrites the live log without the purged records.

The summary record schema is intentionally compact:

    {
      "type":          "summary",
      "window_start":  "2026-04-09T00:00:00Z",
      "window_end":    "2026-04-09T23:59:59Z",
      "hook":          "mutation-method-blocker",
      "decision":      "block",
      "count":         42,
      "p50_latency":   18.4,
      "p95_latency":   72.1,
      "top_detectors": [["array.push", 27], ["object.assign", 9]]
    }

Suggested cron entry (also documented in README.md):

    0 4 * * * python3 ~/.claude/scripts/audit_log_compact.py --retention-days 30

The script never raises on a malformed line. Bad records are skipped.
Atomic rewrite uses a temp file plus rename so a crash mid-run leaves
the original log intact.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from collections import defaultdict
from typing import Any

DEFAULT_LOG_DIR = os.path.expanduser("~/.claude/logs")
DEFAULT_LOG_PATH = os.path.join(DEFAULT_LOG_DIR, "hooks.log")
DEFAULT_SUMMARY_PATH = os.path.join(DEFAULT_LOG_DIR, "hooks.summary.jsonl")
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _parse_ts(record: dict[str, Any]) -> float | None:
    raw = record.get("ts") or record.get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        return time.mktime(time.strptime(raw, TS_FORMAT))
    except (ValueError, OverflowError):
        return None


def _read_records(log_path: str) -> list[tuple[dict[str, Any], str]]:
    items: list[tuple[dict[str, Any], str]] = []
    if not os.path.exists(log_path):
        return items
    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.rstrip("\n")
            if not stripped.strip():
                continue
            try:
                rec = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict):
                continue
            items.append((rec, stripped))
    return items


def _bucket_key(rec: dict[str, Any], ts: float) -> tuple[str, str, str]:
    day = time.strftime("%Y-%m-%d", time.gmtime(ts))
    hook = str(rec.get("hook", "unknown"))
    decision = str(rec.get("decision_class") or rec.get("decision") or "unknown")
    return (day, hook, decision)


def _summary_for_bucket(
    bucket_key: tuple[str, str, str], records: list[dict[str, Any]]
) -> dict[str, Any]:
    day, hook, decision = bucket_key
    latencies = [
        float(r["latency_ms"])
        for r in records
        if isinstance(r.get("latency_ms"), (int, float))
    ]
    detector_counter: dict[str, int] = defaultdict(int)
    for r in records:
        det = r.get("detector") or r.get("detector_tag")
        if isinstance(det, str) and det:
            for tag in det.split(","):
                head = tag.split(":", 1)[0].strip()
                if head:
                    detector_counter[head] += 1
    top_detectors = sorted(
        detector_counter.items(), key=lambda kv: kv[1], reverse=True
    )[:5]
    summary: dict[str, Any] = {
        "type": "summary",
        "window_start": f"{day}T00:00:00Z",
        "window_end": f"{day}T23:59:59Z",
        "hook": hook,
        "decision": decision,
        "count": len(records),
        "top_detectors": top_detectors,
    }
    if latencies:
        summary["p50_latency"] = round(statistics.median(latencies), 2)
        if len(latencies) >= 2:
            sorted_lat = sorted(latencies)
            summary["p95_latency"] = round(
                sorted_lat[max(0, int(len(sorted_lat) * 0.95) - 1)], 2
            )
        else:
            summary["p95_latency"] = round(latencies[0], 2)
    return summary


def compact(
    log_path: str,
    summary_path: str,
    retention_days: int,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Summarize and purge stale records.

    Returns counts: { 'kept', 'summarized', 'buckets' }.
    """
    cutoff = time.time() - retention_days * 86400
    items = _read_records(log_path)
    keep_lines: list[str] = []
    by_bucket: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for rec, raw in items:
        ts = _parse_ts(rec)
        if ts is None or ts >= cutoff:
            keep_lines.append(raw)
            continue
        by_bucket[_bucket_key(rec, ts)].append(rec)

    summaries = [_summary_for_bucket(k, v) for k, v in sorted(by_bucket.items())]

    if dry_run:
        return {
            "kept": len(keep_lines),
            "summarized": sum(len(v) for v in by_bucket.values()),
            "buckets": len(summaries),
        }

    if summaries:
        os.makedirs(os.path.dirname(summary_path), exist_ok=True)
        with open(summary_path, "a", encoding="utf-8") as fh:
            for s in summaries:
                fh.write(json.dumps(s, sort_keys=True) + "\n")

    if by_bucket:
        log_dir = os.path.dirname(log_path) or "."
        fd, tmp_path = tempfile.mkstemp(dir=log_dir, prefix="hooks.log.tmp.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                for line in keep_lines:
                    fh.write(line + "\n")
            os.replace(tmp_path, log_path)
        except OSError:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise

    return {
        "kept": len(keep_lines),
        "summarized": sum(len(v) for v in by_bucket.values()),
        "buckets": len(summaries),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compact ~/.claude/logs/hooks.log")
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument("--log-path", default=DEFAULT_LOG_PATH)
    parser.add_argument("--summary-path", default=DEFAULT_SUMMARY_PATH)
    parser.add_argument(
        "--dry-run", action="store_true", help="report counts without rewriting"
    )
    args = parser.parse_args()
    counts = compact(
        args.log_path,
        args.summary_path,
        args.retention_days,
        dry_run=args.dry_run,
    )
    sys.stdout.write(json.dumps(counts, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
