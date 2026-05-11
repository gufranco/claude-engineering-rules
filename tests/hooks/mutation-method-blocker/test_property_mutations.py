"""Property, computed, index, compound, and increment mutation coverage.

Item 118 of the plan.
"""

from __future__ import annotations

import pytest

from conftest import make_edit_payload, make_write_payload

PROPERTY_BLOCKED: list[tuple[str, str, str]] = [
    ("direct", "obj.prop = 1", "property.assignment"),
    ("computed-string", "obj['prop'] = 1", "property.computed"),
    ("computed-index", "arr[0] = 1", "property.computed"),
    ("compound-plus", "obj.count += 1", "property.compound"),
    ("compound-minus", "obj.count -= 1", "property.compound"),
    ("compound-times", "obj.count *= 2", "property.compound"),
    ("compound-div", "obj.count /= 2", "property.compound"),
    ("compound-pow", "obj.count **= 2", "property.compound"),
    ("compound-bitand", "obj.flags &= mask", "property.compound"),
    ("compound-bitor", "obj.flags |= mask", "property.compound"),
    ("compound-nullish", "obj.value ??= fallback", "property.compound"),
    ("compound-and", "obj.value &&= other", "property.compound"),
    ("compound-or", "obj.value ||= other", "property.compound"),
    ("postfix-incr", "obj.count++", "property.increment"),
    ("postfix-decr", "obj.count--", "property.increment"),
    ("prefix-incr", "++obj.count", "property.increment-prefix"),
    ("prefix-decr", "--obj.count", "property.increment-prefix"),
    ("compound-index-plus", "arr[i] += 1", "property.compound-index"),
    ("compound-index-times", "arr[i] *= 2", "property.compound-index"),
]


@pytest.mark.parametrize(("label", "snippet", "detector"), PROPERTY_BLOCKED)
def test_property_mutation_blocks(run_hook, label, snippet, detector):
    # Arrange
    payload = make_edit_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{label}: expected block, got {code}\n{stderr}"
    assert detector in stderr, f"{label}: detector {detector} missing"


PROPERTY_ALLOWED: list[tuple[str, str]] = [
    ("rest-spread", "const next = { ...obj, prop: 1 }"),
    ("computed-spread", "const next = { ...obj, [key]: 1 }"),
    ("array-with", "const next = arr.with(0, value)"),
    ("array-map", "const next = arr.map((v, i) => i === 0 ? value : v)"),
    ("object-literal", "const obj = { a: 1, b: 2 }"),
    ("class-field", "class Foo { count = 0; }"),
    ("type-annotation", "const x: Record<string, number> = {}"),
    ("equality", "if (obj.prop === 1) doThing()"),
    ("string-equals", "log('value === yes')"),
    (
        "acc-allowlist",
        "const result = arr.reduce((acc, x) => { acc.foo = x; return acc; }, {})",
    ),
    ("acc-compound", "arr.reduce((acc, x) => { acc.count += 1; return acc; }, {})"),
    ("ctx-allowlist", "function middleware(ctx) { ctx.user = loadUser(); }"),
    ("req-allowlist", "function middleware(req) { req.user = loadUser(); }"),
    ("draft-allowlist", "produce(state, draft => { draft.count = 1; })"),
]


@pytest.mark.parametrize(("label", "snippet"), PROPERTY_ALLOWED)
def test_property_allowed_passes(run_hook, label, snippet):
    # Arrange
    payload = make_edit_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"{label}: unexpected block\n{stderr}"


def test_object_initializer_does_not_trigger(run_hook):
    # Arrange
    content = """export const palette = {
  primary: '#000',
  secondary: '#fff',
  accent: 'rebeccapurple',
};
"""
    payload = make_write_payload("/repo/src/palette.ts", content)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr


def test_property_assignment_inside_class_constructor_blocks(run_hook):
    # Arrange
    snippet = "this.tally = 0"
    payload = make_edit_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "property.assignment" in stderr
