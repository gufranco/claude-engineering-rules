"""Array mutation detector coverage.

Validates each of the array prototype mutation methods in plan items 13-26
plus bracket-string dispatch (item 25). Each table entry pairs a known-bad
TypeScript snippet with a known-good counterpart so the detector's fence
stays clear in both directions.
"""

from __future__ import annotations

import pytest

from conftest import make_edit_payload, make_write_payload

ARRAY_BLOCKED_CASES: list[tuple[str, str, str]] = [
    ("push", "items.push(x)", "array.push"),
    ("sort", "items.sort()", "array.sort"),
    ("pop", "items.pop()", "array.pop"),
    ("shift", "items.shift()", "array.shift"),
    ("unshift", "items.unshift(x)", "array.unshift"),
    ("splice", "items.splice(0, 1)", "array.splice"),
    ("reverse", "items.reverse()", "array.reverse"),
    ("fill", "items.fill(0)", "array.fill"),
    ("copyWithin", "items.copyWithin(0, 1)", "array.copyWithin"),
    ("bracket-push", 'items["push"](x)', "array.bracket-dispatch.push"),
    ("bracket-sort", "items['sort']()", "array.bracket-dispatch.sort"),
]


@pytest.mark.parametrize(("label", "snippet", "detector"), ARRAY_BLOCKED_CASES)
def test_array_mutating_method_is_blocked(run_hook, label, snippet, detector):
    # Arrange
    payload = make_edit_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{label}: expected block, got exit {code}"
    assert detector in stderr, f"{label}: detector {detector} not in stderr"


ARRAY_ALLOWED_CASES: list[tuple[str, str]] = [
    ("toSorted", "const sorted = items.toSorted()"),
    ("toReversed", "const reversed = items.toReversed()"),
    ("toSpliced", "const next = items.toSpliced(0, 1)"),
    ("with", "const next = items.with(0, value)"),
    ("spread-push", "const next = [...items, value]"),
    ("filter", "const next = items.filter(x => x > 0)"),
    ("map", "const next = items.map(x => x * 2)"),
    ("router-push", "router.push('/home')"),
    ("history-push", "history.push('/home')"),
    ("stream-push", "stream.push(chunk)"),
    ("logs-push", "logs.push(entry)"),
    ("results-push", "results.push(record)"),
    ("ws-push", "ws.push(msg)"),
    ("queue-push", "queue.push(job)"),
]


@pytest.mark.parametrize(("label", "snippet"), ARRAY_ALLOWED_CASES)
def test_array_allowed_pattern_passes(run_hook, label, snippet):
    # Arrange
    payload = make_edit_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"{label}: expected allow, got exit {code}\nstderr: {stderr}"


def test_string_literal_mentioning_push_is_not_flagged(run_hook):
    # Arrange
    payload = make_edit_payload("/repo/src/app.ts", 'log("arr.push(x) is forbidden")')

    # Act
    code, _ = run_hook(payload)

    # Assert
    assert code == 0


def test_comment_mentioning_push_is_not_flagged(run_hook):
    # Arrange
    payload = make_edit_payload(
        "/repo/src/app.ts", "// items.push(x) -- legacy reference"
    )

    # Act
    code, _ = run_hook(payload)

    # Assert
    assert code == 0


def test_chained_array_mutation(run_hook):
    # Arrange
    payload = make_edit_payload("/repo/src/app.ts", "obj.list.push(value)")

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "array.push" in stderr


def test_full_file_write_with_multiple_array_mutations(run_hook):
    # Arrange
    content = """export function broken(items: number[]): number[] {
  items.push(1);
  items.sort();
  items.reverse();
  return items;
}
"""
    payload = make_write_payload("/repo/src/broken.ts", content)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "array.push" in stderr
    assert "array.sort" in stderr
    assert "array.reverse" in stderr
