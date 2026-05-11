"""Object / Reflect / delete / global mutation coverage.

Item 119 of the plan. Validates Object.assign target mutation, defineProperty
family, setPrototypeOf, the four Reflect mutators, the delete operator, and
global writes (globalThis, window, self, process.env).
"""

from __future__ import annotations

import pytest

from conftest import make_edit_payload

OBJECT_BLOCKED: list[tuple[str, str, str]] = [
    ("assign-target", "Object.assign(existing, source)", "object.assign"),
    ("assign-this", "Object.assign(this, patch)", "object.assign"),
    (
        "define-property",
        "Object.defineProperty(target, 'k', { value: 1 })",
        "object.defineProperty",
    ),
    (
        "define-properties",
        "Object.defineProperties(target, { k: { value: 1 } })",
        "object.defineProperties",
    ),
    (
        "set-prototype-of",
        "Object.setPrototypeOf(target, base)",
        "object.setPrototypeOf",
    ),
    ("reflect-set", "Reflect.set(target, 'k', 1)", "reflect.set"),
    ("reflect-delete", "Reflect.deleteProperty(target, 'k')", "reflect.deleteProperty"),
    (
        "reflect-define",
        "Reflect.defineProperty(target, 'k', { value: 1 })",
        "reflect.defineProperty",
    ),
    (
        "reflect-set-proto",
        "Reflect.setPrototypeOf(target, base)",
        "reflect.setPrototypeOf",
    ),
    ("delete-prop", "delete obj.prop", "delete-operator"),
    ("delete-computed", "delete obj['prop']", "delete-operator"),
    ("delete-index", "delete arr[0]", "delete-operator"),
    ("global-globalthis", "globalThis.bar = 2", "global.assignment"),
    ("global-process-env", "process.env.MY_VAR = 'x'", "global.assignment"),
]


OBJECT_OUT_OF_SCOPE: list[tuple[str, str]] = [
    ("window-property", "window.foo = 1"),
    ("self-property", "self.baz = 3"),
    ("document-property", "document.title = 'x'"),
]


@pytest.mark.parametrize(("label", "snippet"), OBJECT_OUT_OF_SCOPE)
def test_dom_and_web_api_writes_out_of_scope(run_hook, label, snippet):
    """`window.*`, `self.*`, and `document.*` writes are documented
    out-of-scope per `rules/lang/typescript-immutability.md` (DOM and
    Web API Stance). They must not block.
    """
    # Arrange
    payload = make_edit_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"{label}: expected allow, got {code}\n{stderr}"


@pytest.mark.parametrize(("label", "snippet", "detector"), OBJECT_BLOCKED)
def test_object_utility_mutation_is_blocked(run_hook, label, snippet, detector):
    # Arrange
    payload = make_edit_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{label}: expected block, got {code}\n{stderr}"
    assert detector in stderr, f"{label}: detector {detector} missing"


OBJECT_ALLOWED: list[tuple[str, str]] = [
    ("assign-fresh-empty", "const merged = Object.assign({}, base, patch)"),
    ("assign-new-object", "const merged = Object.assign(new Object(), base, patch)"),
    ("assign-object-create", "const merged = Object.assign(Object.create(null), base)"),
    ("spread-merge", "const merged = { ...base, ...patch }"),
    ("destructured-rest", "const { discarded, ...rest } = obj"),
    (
        "filter-by-key",
        "const next = Object.fromEntries(Object.entries(obj).filter(([k]) => k !== 'x'))",
    ),
]


@pytest.mark.parametrize(("label", "snippet"), OBJECT_ALLOWED)
def test_object_utility_allowed_passes(run_hook, label, snippet):
    # Arrange
    payload = make_edit_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"{label}: unexpected block\n{stderr}"
