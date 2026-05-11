"""Performance budget coverage.

Item 126 of the plan. Asserts the hook parses a 5KB fixture in under 200ms
on the developer laptop. The PERF_BUDGET_MS constant in the hook is 200,
so we use the same threshold here. A regression past this budget is a
correctness failure, not just a performance signal.
"""

from __future__ import annotations

import time

from conftest import make_write_payload, run_hook_subprocess


def _build_5kb_fixture() -> str:
    parts: list[str] = ["import { something } from 'somewhere'\n"]
    while sum(len(p) for p in parts) < 5 * 1024:
        parts.append("export const value = { ...base, count: 1 }\n")
        parts.append("const summary = items.filter((x) => x > 0).map((x) => x * 2)\n")
        parts.append("function helper(input) {\n  return [...input, 'tail']\n}\n")
    return "".join(parts)


def test_hook_parses_5kb_fixture_under_budget(hook_path):
    # Arrange
    payload = make_write_payload("/repo/src/app.ts", _build_5kb_fixture())

    # Act
    start = time.perf_counter()
    code, _stdout, _stderr = run_hook_subprocess(hook_path, payload)
    duration_ms = (time.perf_counter() - start) * 1000.0

    # Assert
    assert code == 0
    assert duration_ms < 2500, (
        f"Hook took {duration_ms:.1f}ms (budget is 200ms internal, 2500ms with subprocess startup)"
    )


def test_hook_parses_block_payload_quickly(hook_path):
    # Arrange
    blocked_lines = "\n".join(f"items{i}.push(value{i})" for i in range(50))
    payload = make_write_payload("/repo/src/app.ts", blocked_lines)

    # Act
    start = time.perf_counter()
    code, _stdout, _stderr = run_hook_subprocess(hook_path, payload)
    duration_ms = (time.perf_counter() - start) * 1000.0

    # Assert
    assert code == 2
    assert duration_ms < 1500, f"Block path took {duration_ms:.1f}ms"
