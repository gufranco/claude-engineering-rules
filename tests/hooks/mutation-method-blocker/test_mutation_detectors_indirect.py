from __future__ import annotations

import pytest

from conftest import make_edit_payload

INDIRECT_BLOCKED: list[tuple[str, str, str]] = [
    (
        "prototype-call",
        "Array.prototype.push.call(items, 1);",
        "array.mutator-indirect",
    ),
    ("literal-apply", "[].splice.apply(items, [0, 1]);", "array.mutator-indirect"),
    ("bound-method", "const add = items.push.bind(items);", "array.mutator-indirect"),
    (
        "map-prototype",
        "Map.prototype.set.call(cache, key, value);",
        "array.mutator-indirect",
    ),
    ("array-swap", "[o.a, o.b] = [o.b, o.a];", "property.destructure-target"),
    ("object-pattern", "({ a: o.x } = src);", "property.destructure-target"),
    (
        "indexed-swap",
        "[arr[0], arr[1]] = [arr[1], arr[0]];",
        "property.destructure-target",
    ),
    ("for-of-member", "for (o.k of xs) {}", "property.for-target"),
    ("for-in-member", "for (state.key in table) {}", "property.for-target"),
]

INDIRECT_ALLOWED: list[tuple[str, str]] = [
    ("const-destructure", "const [a, b] = pair;"),
    ("local-swap", "const [first, second] = [second0, first0];"),
    ("const-for-of", "for (const k of xs) {}"),
    ("non-mutating-call", "const doubled = Array.prototype.map.call(xs, double);"),
    ("comparison", "if ([o.a] == other) {}"),
    ("unclosed-array", "[o.a, o.b,"),
]


@pytest.mark.parametrize(("label", "snippet", "detector"), INDIRECT_BLOCKED)
def test_indirect_mutation_blocks(run_hook, label, snippet, detector):
    # Arrange
    payload = make_edit_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert (code, detector in stderr) == (2, True), f"{label}\n{stderr}"


@pytest.mark.parametrize(("label", "snippet"), INDIRECT_ALLOWED)
def test_non_mutating_shapes_pass(run_hook, label, snippet):
    # Arrange
    payload = make_edit_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"{label}\n{stderr}"
