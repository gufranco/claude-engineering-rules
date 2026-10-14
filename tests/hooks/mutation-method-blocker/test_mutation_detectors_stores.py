from __future__ import annotations

import sys
from pathlib import Path

from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_detectors_stores import (  # noqa: E402
    detect_effect_ts_ref_value_assign,
    detect_nanostores_computed_write,
    detect_recoil_deprecation_pointer,
    detect_svelte_derived_reassign,
    detect_tanstack_store_state_write,
    detect_vue_shallow_readonly_nested_write,
)


def _source(faker: Faker) -> str:
    return f"/repo/src/{faker.word()}.svelte.ts"


def test_svelte_derived_reassign_is_flagged(faker: Faker) -> None:
    # Arrange
    text = "let total = $derived(a + b);\ntotal = 3;\n"

    # Act
    hits = detect_svelte_derived_reassign(text, "ts", _source(faker))

    # Assert
    assert [(h.line, h.col, h.metadata["name"]) for h in hits] == [(2, 1, "total")]


def test_svelte_without_derived_bindings_is_clean(faker: Faker) -> None:
    # Arrange
    text = "let total = $state(0);\ntotal = 3;\n"

    # Act
    hits = detect_svelte_derived_reassign(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_effect_ts_ref_value_write_is_flagged(faker: Faker) -> None:
    # Arrange
    text = "import { Ref } from 'effect';\nconst counter = Ref.make(0);\ncounter.value = 1;\n"

    # Act
    hits = detect_effect_ts_ref_value_assign(text, "ts", _source(faker))

    # Assert
    assert [(h.detector, h.line) for h in hits] == [("effect-ts.ref-value-assign", 3)]


def test_effect_ts_requires_an_effect_import(faker: Faker) -> None:
    # Arrange
    text = "const counter = Ref.make(0);\ncounter.value = 1; // effect\n"

    # Act
    hits = detect_effect_ts_ref_value_assign(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_nanostores_computed_set_is_flagged(faker: Faker) -> None:
    # Arrange
    text = "import { computed } from 'nanostores';\nconst total = computed(a, f);\ntotal.set(1);\n"

    # Act
    hits = detect_nanostores_computed_write(text, "ts", _source(faker))

    # Assert
    assert [(h.line, h.metadata["method"]) for h in hits] == [(3, "set")]


def test_tanstack_store_state_write_reports_the_chain(faker: Faker) -> None:
    # Arrange
    text = "import { Store } from '@tanstack/store';\nconst s = new Store({});\ns.state.count = 1;\n"

    # Act
    hits = detect_tanstack_store_state_write(text, "ts", _source(faker))

    # Assert
    assert [(h.line, h.metadata["chain"]) for h in hits] == [(3, ".count")]


def test_vue_shallow_readonly_flags_only_nested_writes(faker: Faker) -> None:
    # Arrange
    text = "const view = shallowReadonly(state);\nview.a = 1;\nview.a.b = 2;\n"

    # Act
    hits = detect_vue_shallow_readonly_nested_write(text, "ts", _source(faker))

    # Assert
    assert [(h.line, h.metadata["chain"]) for h in hits] == [(3, ".a.b")]


def test_recoil_import_yields_one_info_pointer(faker: Faker) -> None:
    # Arrange
    text = "import { atom } from 'recoil';\nimport { selector } from 'recoil';\n"

    # Act
    hits = detect_recoil_deprecation_pointer(text, "ts", _source(faker))

    # Assert
    assert [(h.detector, h.line) for h in hits] == [("recoil.deprecation-pointer", 1)]


def test_recoil_mention_without_import_is_clean(faker: Faker) -> None:
    # Arrange
    text = "const recoil = 1;\n"

    # Act
    hits = detect_recoil_deprecation_pointer(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_tanstack_import_without_a_store_is_clean(faker: Faker) -> None:
    # Arrange
    text = "import { Store } from '@tanstack/store';\ns.state.count = 1;\n"

    # Act
    hits = detect_tanstack_store_state_write(text, "ts", _source(faker))

    # Assert
    assert hits == []
