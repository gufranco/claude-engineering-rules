from __future__ import annotations

import statistics
import time
from pathlib import Path

from conftest import make_write_payload, run_hook_subprocess

SAMPLE_RUNS = 5
MEDIAN_BUDGET_MS = 2500.0
FIXTURE_BYTES = 5 * 1024
BLOCKED_LINES = 50


def _build_5kb_fixture() -> str:
    parts: list[str] = ["import { something } from 'somewhere'\n"]
    while sum(len(p) for p in parts) < FIXTURE_BYTES:
        parts.append("export const value = { ...base, count: 1 }\n")
        parts.append("const summary = items.filter((x) => x > 0).map((x) => x * 2)\n")
        parts.append("function helper(input) {\n  return [...input, 'tail']\n}\n")
    return "".join(parts)


def _sample(hook_path: Path, payload: dict) -> tuple[set[int], float]:
    codes: set[int] = set()
    samples_ms: list[float] = []
    for _ in range(SAMPLE_RUNS):
        start = time.perf_counter()
        code, _stdout, _stderr = run_hook_subprocess(hook_path, payload)
        samples_ms.append((time.perf_counter() - start) * 1000.0)
        codes.add(code)
    return codes, statistics.median(samples_ms)


def test_allow_path_median_stays_under_budget(hook_path: Path) -> None:
    # Arrange
    payload = make_write_payload("/repo/src/app.ts", _build_5kb_fixture())

    # Act
    codes, median_ms = _sample(hook_path, payload)

    # Assert
    assert codes == {0}
    assert median_ms < MEDIAN_BUDGET_MS, f"median {median_ms:.1f}ms"


def test_block_path_median_stays_under_budget(hook_path: Path) -> None:
    # Arrange
    lines = "\n".join(f"items{i}.push(value{i})" for i in range(BLOCKED_LINES))
    payload = make_write_payload("/repo/src/app.ts", lines)

    # Act
    codes, median_ms = _sample(hook_path, payload)

    # Assert
    assert codes == {2}
    assert median_ms < MEDIAN_BUDGET_MS, f"median {median_ms:.1f}ms"
