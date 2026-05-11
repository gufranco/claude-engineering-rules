"""Summarize ~/.claude/logs/hooks.log into a digest.

Spec: `specs/2026-05-09-claude-config-state-of-art/plan.md` 1.3.3.

The audit log captures one JSON object per line. Over time it grows large
enough that a human cannot scan it directly. This script rolls the log up
into a compact summary:

    - total record count over the window
    - counts grouped by hook and by decision
    - latency p50/p95/p99 per hook (when `latency_ms` is present)
    - false-positive estimate per hook (`suppressed=True` rate)
    - top reasons by count, with their hooks attached
    - top detector tags by count
    - top defect-pattern tags by count

The script reads `~/.claude/logs/hooks.log` and `hooks.log.1` so the rotated
backup is included when present. The CLI accepts `--window 24h` or any
`{N}{s,m,h,d}` form to bound the time range.

Usage:

    python3 scripts/audit_summarize.py --window 24h
    python3 scripts/audit_summarize.py --window 7d --format json
    python3 scripts/audit_summarize.py --log-path /tmp/h.log --top 25

The script never raises on a malformed line. Bad records are silently
skipped so a single corrupted entry never blocks the summary.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from typing import Any

DEFAULT_LOG_DIR = os.path.expanduser("~/.claude/logs")
DEFAULT_LOG_PATH = os.path.join(DEFAULT_LOG_DIR, "hooks.log")
DEFAULT_BACKUP_PATH = DEFAULT_LOG_PATH + ".1"
DEFAULT_TOP = 10
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

_WINDOW_RE = re.compile(r"^(?P<n>\d+)(?P<unit>[smhd])$")
_UNIT_TO_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_window(spec: str | None) -> int | None:
    """Convert a window like '24h' to a seconds count.

    Returns `None` when `spec` is None or empty (no window restriction).
    Raises `ValueError` when `spec` cannot be parsed.
    """
    if spec is None or spec == "":
        return None
    match = _WINDOW_RE.match(spec.strip())
    if not match:
        raise ValueError(
            f"invalid window spec {spec!r}; expected formats like 24h, 7d, 30m, 90s"
        )
    n = int(match.group("n"))
    unit = match.group("unit")
    return n * _UNIT_TO_SECONDS[unit]


def _parse_ts(ts: str) -> float | None:
    """Return epoch seconds for a record timestamp. None on parse failure."""
    if not isinstance(ts, str):
        return None
    try:
        return time.mktime(time.strptime(ts, TS_FORMAT)) - time.timezone
    except (ValueError, TypeError):
        return None


def iter_records(
    log_paths: Iterable[str],
    *,
    since_epoch: float | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield JSON records from the given log paths.

    `since_epoch` filters out records older than the cutoff. Records with
    a missing or malformed `ts` are excluded when filtering is active and
    included otherwise.
    """
    for path in log_paths:
        if not path or not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    if not isinstance(record, dict):
                        continue
                    if since_epoch is not None:
                        ts = _parse_ts(record.get("ts", ""))
                        if ts is None or ts < since_epoch:
                            continue
                    yield record
        except OSError:
            continue


def _percentile(sorted_values: list[int], p: float) -> int:
    """Compute a percentile on a pre-sorted list. Returns 0 on empty."""
    if not sorted_values:
        return 0
    if len(sorted_values) == 1:
        return int(sorted_values[0])
    rank = (len(sorted_values) - 1) * p
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return int(sorted_values[lo])
    weight = rank - lo
    interpolated = sorted_values[lo] * (1 - weight) + sorted_values[hi] * weight
    return int(round(interpolated))


def _hook_name(record: dict[str, Any]) -> str:
    return str(record.get("hook") or record.get("hook_name") or "unknown")


def _decision(record: dict[str, Any]) -> str:
    return str(record.get("decision_class") or record.get("decision") or "unknown")


def summarize(
    records: Iterable[dict[str, Any]],
    *,
    top: int = DEFAULT_TOP,
) -> dict[str, Any]:
    """Aggregate records into a structured summary."""
    total = 0
    counts_by_hook: Counter[str] = Counter()
    counts_by_decision: Counter[str] = Counter()
    latencies_by_hook: dict[str, list[int]] = defaultdict(list)
    suppressed_by_hook: Counter[str] = Counter()
    samples_by_hook: Counter[str] = Counter()
    reasons: Counter[tuple[str, str]] = Counter()
    detector_tags: Counter[str] = Counter()
    defect_pattern_tags: Counter[str] = Counter()

    for record in records:
        total += 1
        hook = _hook_name(record)
        decision = _decision(record)
        counts_by_hook[hook] += 1
        counts_by_decision[decision] += 1
        samples_by_hook[hook] += 1

        latency = record.get("latency_ms")
        if isinstance(latency, (int, float)) and not isinstance(latency, bool):
            try:
                latencies_by_hook[hook].append(int(latency))
            except (TypeError, ValueError):
                pass

        if record.get("suppressed") is True:
            suppressed_by_hook[hook] += 1

        reason = record.get("reason")
        if isinstance(reason, str) and reason:
            reasons[(reason, hook)] += 1

        detector_tag = record.get("detector_tag") or record.get("detector")
        if isinstance(detector_tag, str) and detector_tag:
            detector_tags[detector_tag] += 1

        defect_pattern = record.get("defect_pattern_tag") or record.get(
            "defect_pattern"
        )
        if isinstance(defect_pattern, str) and defect_pattern:
            defect_pattern_tags[defect_pattern] += 1

    latency_summary: dict[str, dict[str, int]] = {}
    for hook, values in latencies_by_hook.items():
        sorted_values = sorted(values)
        latency_summary[hook] = {
            "n": len(sorted_values),
            "p50": _percentile(sorted_values, 0.50),
            "p95": _percentile(sorted_values, 0.95),
            "p99": _percentile(sorted_values, 0.99),
        }

    false_positive: dict[str, dict[str, float | int]] = {}
    for hook in counts_by_hook:
        suppressed_count = suppressed_by_hook[hook]
        sample_count = samples_by_hook[hook] or 1
        false_positive[hook] = {
            "suppressed_count": suppressed_count,
            "sample_count": samples_by_hook[hook],
            "suppression_rate": round(suppressed_count / sample_count, 4),
        }

    top_reasons = [
        {"reason": reason, "hook": hook, "count": count}
        for (reason, hook), count in reasons.most_common(top)
    ]
    top_detector_tags = [
        {"detector_tag": tag, "count": count}
        for tag, count in detector_tags.most_common(top)
    ]
    top_defect_pattern_tags = [
        {"defect_pattern_tag": tag, "count": count}
        for tag, count in defect_pattern_tags.most_common(top)
    ]

    return {
        "total_records": total,
        "counts_by_hook": dict(counts_by_hook.most_common()),
        "counts_by_decision": dict(counts_by_decision.most_common()),
        "latency_by_hook": latency_summary,
        "false_positive_by_hook": false_positive,
        "top_reasons": top_reasons,
        "top_detector_tags": top_detector_tags,
        "top_defect_pattern_tags": top_defect_pattern_tags,
    }


def _format_table(summary: dict[str, Any]) -> str:
    """Render a compact human-readable table of the summary."""
    lines: list[str] = []
    lines.append(f"Total records: {summary['total_records']}")
    lines.append("")
    lines.append("Counts by hook:")
    for hook, count in summary["counts_by_hook"].items():
        lines.append(f"  {hook:40s} {count}")
    lines.append("")
    lines.append("Counts by decision:")
    for decision, count in summary["counts_by_decision"].items():
        lines.append(f"  {decision:20s} {count}")
    if summary["latency_by_hook"]:
        lines.append("")
        lines.append("Latency by hook (ms):")
        lines.append(f"  {'hook':40s} {'n':>6s} {'p50':>6s} {'p95':>6s} {'p99':>6s}")
        for hook, stats in summary["latency_by_hook"].items():
            lines.append(
                f"  {hook:40s} {stats['n']:>6d} {stats['p50']:>6d} "
                f"{stats['p95']:>6d} {stats['p99']:>6d}"
            )
    lines.append("")
    lines.append("False-positive estimates by hook:")
    for hook, stats in summary["false_positive_by_hook"].items():
        lines.append(
            f"  {hook:40s} suppressed={stats['suppressed_count']:>4d}  "
            f"rate={stats['suppression_rate']:.4f}"
        )
    if summary["top_reasons"]:
        lines.append("")
        lines.append("Top reasons:")
        for entry in summary["top_reasons"]:
            lines.append(
                f"  [{entry['count']:>4d}] {entry['hook']:30s} {entry['reason']}"
            )
    if summary["top_detector_tags"]:
        lines.append("")
        lines.append("Top detector tags:")
        for entry in summary["top_detector_tags"]:
            lines.append(f"  [{entry['count']:>4d}] {entry['detector_tag']}")
    if summary["top_defect_pattern_tags"]:
        lines.append("")
        lines.append("Top defect pattern tags:")
        for entry in summary["top_defect_pattern_tags"]:
            lines.append(f"  [{entry['count']:>4d}] {entry['defect_pattern_tag']}")
    return "\n".join(lines)


def _resolve_log_paths(
    primary: str | None,
    *,
    include_backup: bool = True,
) -> list[str]:
    if primary:
        paths = [primary]
        if include_backup:
            paths.append(primary + ".1")
        return paths
    paths = [DEFAULT_LOG_PATH]
    if include_backup:
        paths.append(DEFAULT_BACKUP_PATH)
    return paths


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Roll up ~/.claude/logs/hooks.log into a digest."
    )
    parser.add_argument(
        "--window",
        default=None,
        help="Only include records within the window (e.g. 24h, 7d, 30m).",
    )
    parser.add_argument(
        "--log-path",
        default=None,
        help="Override the default ~/.claude/logs/hooks.log path.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip hooks.log.1 even when it exists.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP,
        help=f"Number of items to include in top-N lists (default: {DEFAULT_TOP}).",
    )
    parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table).",
    )
    args = parser.parse_args(argv)

    try:
        seconds = parse_window(args.window)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    since_epoch = None if seconds is None else time.time() - seconds
    paths = _resolve_log_paths(args.log_path, include_backup=not args.no_backup)
    summary = summarize(
        iter_records(paths, since_epoch=since_epoch),
        top=max(1, args.top),
    )

    if args.format == "json":
        sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_format_table(summary))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
