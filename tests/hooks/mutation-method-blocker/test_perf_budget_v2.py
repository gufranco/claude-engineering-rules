from __future__ import annotations

import statistics
import time

from conftest import make_write_payload, run_hook_subprocess


SAMPLE_RUNS = 30


def _sample_runs(hook_path, payload: dict, runs: int) -> tuple[list[float], list[int]]:
    samples_ms: list[float] = []
    codes: list[int] = []
    for _ in range(runs):
        start = time.perf_counter()
        code, _stdout, _stderr = run_hook_subprocess(hook_path, payload)
        samples_ms.append((time.perf_counter() - start) * 1000.0)
        codes.append(code)
    return samples_ms, codes


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
    # Arrange
    payload = make_write_payload("/repo/src/app.ts", _build_5kb_fixture())

    # Act
    samples_ms, codes = _sample_runs(hook_path, payload, SAMPLE_RUNS)

    # Assert
    p95 = _percentile(samples_ms, 95.0)
    p99 = _percentile(samples_ms, 99.0)
    mean = statistics.fmean(samples_ms)
    assert codes == [0] * SAMPLE_RUNS
    assert p95 < 2500.0, f"p95 {p95:.1f}ms exceeds 2500ms"
    assert p99 < 3500.0, f"p99 {p99:.1f}ms exceeds 3500ms"
    assert mean < 1800.0, f"mean {mean:.1f}ms exceeds 1800ms"
