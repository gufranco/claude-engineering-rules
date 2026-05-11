#!/usr/bin/env python3
"""Per-fixture latency benchmark for mutation-method-blocker.

Reads every fixture under `tests/corpus/mutation-method-blocker/`, runs the
hook N times per fixture (default 100), and emits a JSON report with
p50/p95/p99/mean latency in milliseconds.

Plan items 234, 235 (D38). Output is consumed by the perf-budget CI job
that asserts the v2 budget: p95 < 180ms with AST on, p99 < 250ms,
mean < 60ms.

Usage:
  python3 scripts/bench_mutation_blocker.py            # 100 iters per fixture
  python3 scripts/bench_mutation_blocker.py --iters 50
  python3 scripts/bench_mutation_blocker.py --output bench.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "tests" / "corpus" / "mutation-method-blocker"
HOOK = ROOT / "hooks" / "mutation-method-blocker.py"


def _percentile(values: list[float], pct: float) -> float:
    """Return the pct-th percentile (0-100) of a list of floats."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if pct <= 0:
        return ordered[0]
    if pct >= 100:
        return ordered[-1]
    rank = (pct / 100.0) * (len(ordered) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


def _run_one(fixture: Path, payload: str) -> float:
    """Execute the hook once against a fixture; return wall time in ms."""
    start = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30.0,
        check=False,
    )
    duration_ms = (time.perf_counter() - start) * 1000.0
    if proc.returncode not in (0, 1, 2):
        raise RuntimeError(
            f"unexpected hook exit {proc.returncode} on {fixture}: {proc.stderr}"
        )
    return duration_ms


def _build_payload(fixture: Path) -> str:
    """Wrap a fixture file as a Write payload the hook understands."""
    text = fixture.read_text(encoding="utf-8")
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(fixture),
            "content": text,
        },
    }
    return json.dumps(payload)


def _bench_fixture(fixture: Path, iters: int) -> dict[str, float | str | int]:
    payload = _build_payload(fixture)
    timings: list[float] = []
    for _ in range(iters):
        timings.append(_run_one(fixture, payload))
    return {
        "fixture": str(fixture.relative_to(ROOT)),
        "iters": iters,
        "p50": round(statistics.median(timings), 2),
        "p95": round(_percentile(timings, 95.0), 2),
        "p99": round(_percentile(timings, 99.0), 2),
        "mean": round(statistics.fmean(timings), 2),
        "min": round(min(timings), 2),
        "max": round(max(timings), 2),
    }


def _gather_fixtures() -> list[Path]:
    if not CORPUS.exists():
        return []
    return sorted(p for p in CORPUS.rglob("*.ts") if p.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description="mutation-method-blocker benchmark")
    parser.add_argument("--iters", type=int, default=100)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--budget-p95", type=float, default=180.0, help="p95 budget in ms (D38)"
    )
    parser.add_argument(
        "--budget-p99", type=float, default=250.0, help="p99 budget in ms (D38)"
    )
    parser.add_argument(
        "--budget-mean", type=float, default=60.0, help="mean budget in ms (D38)"
    )
    args = parser.parse_args()

    fixtures = _gather_fixtures()
    if not fixtures:
        sys.stderr.write(
            "No fixtures found under tests/corpus/mutation-method-blocker/\n"
        )
        return 1

    fixture_results: list[dict[str, Any]] = [
        _bench_fixture(f, args.iters) for f in fixtures
    ]
    report: dict[str, Any] = {
        "tool": "mutation-method-blocker",
        "iters_per_fixture": args.iters,
        "fixtures": fixture_results,
        "budget": {
            "p95_ms": args.budget_p95,
            "p99_ms": args.budget_p99,
            "mean_ms": args.budget_mean,
        },
    }

    aggregate_p95 = max(float(r["p95"]) for r in fixture_results)
    aggregate_p99 = max(float(r["p99"]) for r in fixture_results)
    aggregate_mean = max(float(r["mean"]) for r in fixture_results)
    report["aggregate"] = {
        "p95_ms": round(aggregate_p95, 2),
        "p99_ms": round(aggregate_p99, 2),
        "mean_ms": round(aggregate_mean, 2),
    }

    output = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    sys.stdout.write(output + "\n")

    failures = []
    if aggregate_p95 > args.budget_p95:
        failures.append(f"p95 {aggregate_p95:.2f}ms > {args.budget_p95:.2f}ms")
    if aggregate_p99 > args.budget_p99:
        failures.append(f"p99 {aggregate_p99:.2f}ms > {args.budget_p99:.2f}ms")
    if aggregate_mean > args.budget_mean:
        failures.append(f"mean {aggregate_mean:.2f}ms > {args.budget_mean:.2f}ms")
    if failures:
        sys.stderr.write("Perf budget violation:\n  " + "\n  ".join(failures) + "\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
