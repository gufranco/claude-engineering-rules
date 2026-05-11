"""Map / Set / WeakMap / WeakSet mutation coverage.

Item 117 of the plan. Confirms each prototype mutation method blocks and
that immutable replacements (`new Map([...])`) pass.
"""

from __future__ import annotations

import pytest

from conftest import make_edit_payload

MAP_BLOCKED: list[tuple[str, str]] = [
    ("const m = new Map<string, number>()\nm.set(key, value)", "collection.map.set"),
    ("const m = new Map<string, number>()\nm.delete(key)", "collection.map.delete"),
    ("const m = new Map<string, number>()\nm.clear()", "collection.map.clear"),
]

SET_BLOCKED: list[tuple[str, str]] = [
    ("const s = new Set<string>()\ns.add(value)", "collection.set.add"),
    ("const s = new Set<string>()\ns.delete(value)", "collection.set.delete"),
    ("const s = new Set<string>()\ns.clear()", "collection.set.clear"),
]

WEAK_BLOCKED: list[tuple[str, str]] = [
    (
        "const wm = new WeakMap<object, number>()\nwm.set(obj, value)",
        "collection.weakmap.set",
    ),
    ("const ws = new WeakSet<object>()\nws.add(obj)", "collection.weakset.add"),
    ("const ws = new WeakSet<object>()\nws.delete(obj)", "collection.weakset.delete"),
]


@pytest.mark.parametrize(
    ("snippet", "detector"), MAP_BLOCKED + SET_BLOCKED + WEAK_BLOCKED
)
def test_map_or_set_mutation_is_blocked(run_hook, snippet, detector):
    # Arrange
    payload = make_edit_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"unexpected exit {code}\n{stderr}"
    assert detector in stderr, f"detector {detector} missing in:\n{stderr}"


COLLECTION_ALLOWED: list[str] = [
    "const next = new Map([...m, [k, v]])",
    "const next = new Set([...s, v])",
    "const next = new Map([...m].filter(([key]) => key !== 'x'))",
    "const value = m.get(k)",
    "const present = s.has(v)",
    "for (const [k, v] of m.entries()) console.log(k, v)",
    "const union = a.union(b)",
    "const inter = a.intersection(b)",
]


@pytest.mark.parametrize("snippet", COLLECTION_ALLOWED)
def test_collection_allowed_pattern_passes(run_hook, snippet):
    # Arrange
    payload = make_edit_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"unexpected block:\n{stderr}"
