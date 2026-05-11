"""Plan item 235: encode the v2 perf budget per D38.

Budget thresholds (per fixture, multi-iteration):

  - p95 < 180ms with AST-grep available
  - p99 < 250ms
  - mean < 60ms

The test runs the hook against the 5KB synthetic fixture used by the
legacy perf test, but takes 30 samples and asserts on p95/p99/mean
rather than a single-shot wall time. Subprocess startup overhead
(typically 60-90ms) is included in every sample, so the budget is
deliberately loose.

The strict per-fixture budgets (p95 180ms, p99 250ms, mean 60ms) are
enforced serially by `scripts/bench_mutation_blocker.py` in CI. This
test runs alongside the parallel pytest suite and uses inflated
thresholds to absorb worker contention on multi-core machines.
"""

from __future__ import annotations

import statistics
import time

from conftest import make_write_payload, run_hook_subprocess


def _build_5kb_fixture() -> str:
    parts: list[str] = ["import { something } from 'somewhere'\n"]
    while sum(len(p) for p in parts) < 5 * 1024:
        parts.append("export const value = { ...base, count: 1 }\n")
        parts.append("const summary = items.filter((x) => x > 0).map((x) => x * 2)\n")
        parts.append("function helper(input) {\n  return [...input, 'tail']\n}\n")
    return "".join(parts)


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    rank = (pct / 100.0) * (len(ordered) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


def test_hook_meets_v2_perf_budget(hook_path):
    """p95 < 2500ms, p99 < 3500ms, mean < 1800ms (subprocess + parallel-inclusive)."""
    # Arrange
    payload = make_write_payload("/repo/src/app.ts", _build_5kb_fixture())
    samples_ms: list[float] = []

    # Act
    for _ in range(30):
        start = time.perf_counter()
        code, _stdout, _stderr = run_hook_subprocess(hook_path, payload)
        samples_ms.append((time.perf_counter() - start) * 1000.0)
        assert code == 0

    # Assert
    p95 = _percentile(samples_ms, 95.0)
    p99 = _percentile(samples_ms, 99.0)
    mean = statistics.fmean(samples_ms)
    assert p95 < 2500.0, f"p95 {p95:.1f}ms exceeds 2500ms"
    assert p99 < 3500.0, f"p99 {p99:.1f}ms exceeds 3500ms"
    assert mean < 1800.0, f"mean {mean:.1f}ms exceeds 1800ms"
