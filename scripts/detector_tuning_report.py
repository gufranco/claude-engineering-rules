#!/usr/bin/env python3
"""Detector tuning report (plan item 393).

Reads telemetry from one of three sources and summarises detector
behavior so a maintainer can decide where to tune patterns:

    1. The hook audit log at `~/.claude/logs/hooks.log` (JSON Lines).
    2. An OpenTelemetry trace dump in JSON Lines form (one span per line).
    3. A directory of SARIF documents (one document per file).

The report ranks detectors by three signals:

    - block rate            blocks per million tool calls
    - allow ratio           share of detector hits that were suppressed
                            by an allowlist, scope, or `claude-allow-mutation`
                            marker. High values point to over-eager patterns
    - latency p95           wall time at the 95th percentile, in ms

Detectors with `allow_ratio > 0.5` are flagged as tuning candidates
because every other hit on those detectors is being explicitly waved
through, which suggests the regex is too broad. Detectors with
`latency_p95 > 50ms` are flagged for performance review.

Usage:

    python3 ~/.claude/scripts/detector_tuning_report.py \\
        [--audit ~/.claude/logs/hooks.log] [--otel <jsonl>] \\
        [--sarif <dir>] [--format text|json]

Quarterly cadence: run on the first day of each quarter, archive the
output under `docs/telemetry/<YYYY-Q#>.md`, and tune the detectors with
the worst `allow_ratio` and `latency_p95`.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

DEFAULT_AUDIT_PATH = os.path.expanduser("~/.claude/logs/hooks.log")
ALLOW_RATIO_THRESHOLD = 0.5
LATENCY_P95_THRESHOLD_MS = 50.0
MIN_SAMPLES_FOR_FLAG = 20


@dataclass
class DetectorStats:
    detector: str
    blocks: int = 0
    allows: int = 0
    suppressed: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    confidence_scores: list[int] = field(default_factory=list)
    files: set[str] = field(default_factory=set)

    @property
    def total(self) -> int:
        return self.blocks + self.allows + self.suppressed

    @property
    def allow_ratio(self) -> float:
        denom = self.blocks + self.allows + self.suppressed
        return 0.0 if denom == 0 else (self.allows + self.suppressed) / denom

    @property
    def latency_p50(self) -> float:
        return statistics.median(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def latency_p95(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_lat = sorted(self.latencies_ms)
        idx = max(0, int(round(0.95 * (len(sorted_lat) - 1))))
        return sorted_lat[idx]

    @property
    def avg_confidence(self) -> float:
        if not self.confidence_scores:
            return 0.0
        return sum(self.confidence_scores) / len(self.confidence_scores)


def _ensure_stats(
    by_detector: dict[str, DetectorStats], detector: str
) -> DetectorStats:
    if detector not in by_detector:
        by_detector[detector] = DetectorStats(detector=detector)
    return by_detector[detector]


def _ingest_audit_record(
    by_detector: dict[str, DetectorStats], rec: dict[str, Any]
) -> None:
    """Extract detector data from a single audit-log JSON record."""
    if rec.get("hook") != "mutation-method-blocker":
        return
    decision = rec.get("decision") or rec.get("decision_class") or ""
    raw_det = rec.get("detector") or rec.get("detector_tag") or ""
    if not raw_det:
        return
    pairs = [p.strip() for p in str(raw_det).split(",") if p.strip()]
    for pair in pairs:
        name, _, count = pair.partition(":")
        if not name:
            continue
        try:
            n = int(count) if count else 1
        except ValueError:
            n = 1
        stats = _ensure_stats(by_detector, name)
        if decision == "block":
            stats.blocks += n
        elif decision == "allow":
            stats.allows += n
        elif decision == "suppress":
            stats.suppressed += n
        latency_ms = rec.get("latency_ms") or rec.get("duration_ms") or 0.0
        try:
            stats.latencies_ms.append(float(latency_ms))
        except (TypeError, ValueError):
            pass
        confidence = rec.get("confidence_score")
        if confidence is not None:
            try:
                stats.confidence_scores.append(int(confidence))
            except (TypeError, ValueError):
                pass
        fp = rec.get("file_path") or rec.get("file")
        if fp:
            stats.files.add(fp)


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    out.append(json.loads(stripped))
                except json.JSONDecodeError:
                    continue
    except OSError as exc:
        print(f"detector-tuning: cannot read {path}: {exc}", file=sys.stderr)
    return out


def _load_audit(path: str, by_detector: dict[str, DetectorStats]) -> int:
    records = _read_jsonl(path)
    for rec in records:
        _ingest_audit_record(by_detector, rec)
    return len(records)


def _load_otel(path: str, by_detector: dict[str, DetectorStats]) -> int:
    """Each line is one span with `hook.*` attributes."""
    spans = _read_jsonl(path)
    count = 0
    for span in spans:
        attrs = span.get("attributes") or span
        hook = attrs.get("hook.name") or attrs.get("hook")
        if hook != "mutation-method-blocker":
            continue
        rec = {
            "hook": hook,
            "decision": attrs.get("hook.decision") or "",
            "detector": attrs.get("hook.detector") or "",
            "latency_ms": attrs.get("hook.latency_ms") or 0.0,
            "confidence_score": attrs.get("hook.confidence"),
            "file_path": attrs.get("hook.file"),
        }
        _ingest_audit_record(by_detector, rec)
        count += 1
    return count


def _load_sarif_dir(path: str, by_detector: dict[str, DetectorStats]) -> int:
    """Each SARIF document is treated as one batch of block decisions."""
    count = 0
    if not os.path.isdir(path):
        print(f"detector-tuning: not a directory: {path}", file=sys.stderr)
        return count
    for fname in os.listdir(path):
        full = os.path.join(path, fname)
        if not fname.endswith(".sarif") and not fname.endswith(".json"):
            continue
        try:
            with open(full, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            continue
        for run in doc.get("runs", []):
            for result in run.get("results", []):
                rule = result.get("ruleId") or ""
                if "/" in rule:
                    detector = rule.split("/", 1)[1]
                else:
                    detector = rule
                if not detector:
                    continue
                stats = _ensure_stats(by_detector, detector)
                stats.blocks += 1
                count += 1
                for loc in result.get("locations", []):
                    artifact = loc.get("physicalLocation", {}).get(
                        "artifactLocation", {}
                    )
                    if artifact.get("uri"):
                        stats.files.add(artifact["uri"])
    return count


def _build_recommendations(
    by_detector: dict[str, DetectorStats],
) -> list[dict[str, Any]]:
    """Identify detectors worth tuning."""
    recs: list[dict[str, Any]] = []
    for stats in by_detector.values():
        if stats.total < MIN_SAMPLES_FOR_FLAG:
            continue
        flags = []
        if stats.allow_ratio > ALLOW_RATIO_THRESHOLD:
            flags.append("over-eager")
        if stats.latency_p95 > LATENCY_P95_THRESHOLD_MS:
            flags.append("slow")
        if stats.avg_confidence and stats.avg_confidence < 3.0:
            flags.append("low-confidence")
        if flags:
            recs.append(
                {
                    "detector": stats.detector,
                    "flags": flags,
                    "samples": stats.total,
                    "allow_ratio": round(stats.allow_ratio, 3),
                    "latency_p95_ms": round(stats.latency_p95, 2),
                    "avg_confidence": round(stats.avg_confidence, 2),
                }
            )
    recs.sort(key=lambda r: (-len(r["flags"]), -r["samples"]))
    return recs


def _render_text(
    stats_by_det: dict[str, DetectorStats], recs: list[dict[str, Any]]
) -> str:
    out: list[str] = []
    out.append("detector-tuning report")
    out.append(
        "  detector                              total   block   allow   suppress  "
        "allow%  p50ms  p95ms  conf"
    )
    rows = sorted(stats_by_det.values(), key=lambda s: -s.total)
    for s in rows:
        if s.total == 0:
            continue
        out.append(
            f"  {s.detector:<38}{s.total:>6} {s.blocks:>7} {s.allows:>7} "
            f"{s.suppressed:>9}  {s.allow_ratio * 100:>5.1f} "
            f"{s.latency_p50:>5.1f} {s.latency_p95:>5.1f}  {s.avg_confidence:>4.1f}"
        )
    if recs:
        out.append("")
        out.append("tuning candidates:")
        for rec in recs:
            flags = ", ".join(rec["flags"])
            out.append(
                f"  - {rec['detector']:<32} [{flags}] "
                f"n={rec['samples']} allow_ratio={rec['allow_ratio']} "
                f"p95={rec['latency_p95_ms']}ms conf={rec['avg_confidence']}"
            )
    else:
        out.append("")
        out.append("no tuning candidates above threshold")
    return "\n".join(out)


def _render_json(
    stats_by_det: dict[str, DetectorStats], recs: list[dict[str, Any]]
) -> str:
    payload = {
        "detectors": [
            {
                "detector": s.detector,
                "samples": s.total,
                "blocks": s.blocks,
                "allows": s.allows,
                "suppressed": s.suppressed,
                "allow_ratio": round(s.allow_ratio, 4),
                "latency_p50_ms": round(s.latency_p50, 2),
                "latency_p95_ms": round(s.latency_p95, 2),
                "avg_confidence": round(s.avg_confidence, 2),
                "files": sorted(s.files),
            }
            for s in sorted(stats_by_det.values(), key=lambda s: -s.total)
            if s.total > 0
        ],
        "recommendations": recs,
        "thresholds": {
            "allow_ratio": ALLOW_RATIO_THRESHOLD,
            "latency_p95_ms": LATENCY_P95_THRESHOLD_MS,
            "min_samples_for_flag": MIN_SAMPLES_FOR_FLAG,
        },
    }
    return json.dumps(payload, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit",
        default=DEFAULT_AUDIT_PATH,
        help="Path to the hook audit log (JSON Lines).",
    )
    parser.add_argument(
        "--otel",
        default=None,
        help="Path to an OTel span dump in JSON Lines form.",
    )
    parser.add_argument(
        "--sarif",
        default=None,
        help="Directory containing SARIF documents.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    args = parser.parse_args()

    by_detector: dict[str, DetectorStats] = defaultdict(lambda: DetectorStats(""))
    by_detector.clear()

    total = 0
    if os.path.exists(args.audit):
        total += _load_audit(args.audit, by_detector)
    if args.otel:
        total += _load_otel(args.otel, by_detector)
    if args.sarif:
        total += _load_sarif_dir(args.sarif, by_detector)

    if total == 0:
        print("detector-tuning: no telemetry input found", file=sys.stderr)
        return 1

    recs = _build_recommendations(by_detector)
    if args.format == "json":
        sys.stdout.write(_render_json(dict(by_detector), recs))
    else:
        sys.stdout.write(_render_text(dict(by_detector), recs))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
