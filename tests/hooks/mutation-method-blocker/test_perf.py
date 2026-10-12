from __future__ import annotations

from _helpers.timing import timed
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
    (code, _stdout, _stderr), duration_ms = timed(
        run_hook_subprocess, hook_path, payload
    )

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
    (code, _stdout, _stderr), duration_ms = timed(
        run_hook_subprocess, hook_path, payload
    )

    # Assert
    assert code == 2
    assert duration_ms < 1500, f"Block path took {duration_ms:.1f}ms"
