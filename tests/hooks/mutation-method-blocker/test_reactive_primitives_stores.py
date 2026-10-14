from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.mutation_allowlists import (  # noqa: E402
    collect_state_mgmt_receivers,
    collect_svelte_state_raw_receivers,
    is_in_state_mgmt_scope,
    is_state_mgmt_filename,
)


def test_solid_store_with_produce_recognized() -> None:
    # Arrange
    text = (
        'import { createStore, produce, unwrap } from "solid-js/store";\n'
        "const [state, setState] = createStore({ items: [] });\n"
        "setState(produce(s => { s.items.push(item); }));\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "comp.tsx")

    # Assert
    assert scope is True
    assert label in ("solid-produce", "solid-store")


def test_solid_reconcile_distinct_from_produce() -> None:
    # Arrange
    text = (
        'import { createStore, reconcile } from "solid-js/store";\n'
        "const [state, setState] = createStore({ items: [] });\n"
        "setState(reconcile(nextFromServer));\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "comp.tsx")

    # Assert
    assert scope is True
    assert label == "solid-reconcile"


def test_solid_produce_label_when_both_present() -> None:
    # Arrange
    text = (
        'import { createStore, produce, reconcile } from "solid-js/store";\n'
        "const [state, setState] = createStore({ items: [] });\n"
        "setState(produce(s => { s.items.push(item); }));\n"
        "setState(reconcile(nextFromServer));\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "comp.tsx")

    # Assert
    assert scope is True
    assert label == "solid-produce"


def test_tc39_signals_proposal_recognized() -> None:
    # Arrange
    text = (
        'import { Signal } from "signal-polyfill";\n'
        "const counter = new Signal.State(0);\n"
        "counter.set(5);\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "store.ts")

    # Assert
    assert scope is True
    assert label == "tc39-signals"


def test_tc39_signals_proposal_recognized_receivers() -> None:
    # Arrange
    text = (
        'import { Signal } from "signal-polyfill";\n'
        "const counter = new Signal.State(0);\n"
        "counter.set(5);\n"
    )

    # Act
    receivers = collect_state_mgmt_receivers(text, "store.ts")

    # Assert
    assert "counter" in receivers["tc39-signals"]


def test_tc39_signals_negative_without_import() -> None:
    # Arrange
    text = "const counter = new Signal.State(0);\ncounter.set(5);\n"

    # Act
    _scope, label = is_in_state_mgmt_scope(text, "plain.ts")

    # Assert
    assert label != "tc39-signals"


def test_effect_ts_gen_recognized() -> None:
    # Arrange
    text = (
        'import { Effect, Ref } from "effect";\n'
        "const program = Effect.gen(function*() {\n"
        "  const ref = yield* Ref.make(0);\n"
        "  yield* Ref.update(ref, n => n + 1);\n"
        "});\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "program.ts")

    # Assert
    assert scope is True
    assert label == "effect-ts"


def test_effect_ts_ref_recognized() -> None:
    # Arrange
    text = 'import { Ref } from "effect";\nconst ref = Ref.make(0);\nRef.set(ref, 5);\n'

    # Act
    scope, label = is_in_state_mgmt_scope(text, "ref.ts")

    # Assert
    assert scope is True
    assert label == "effect-ts"


def test_effect_ts_negative_without_import() -> None:
    # Arrange
    text = "const ref = Ref.make(0);\nRef.set(ref, 5);\n"

    # Act
    _scope, label = is_in_state_mgmt_scope(text, "plain.ts")

    # Assert
    assert label != "effect-ts"


def test_effect_filename_allowlisted() -> None:
    # Arrange
    file_path = "src/programs/orders.effect.ts"

    # Act
    result = is_state_mgmt_filename(file_path)

    # Assert
    assert result is True


def test_angular_linkedsignal_recognized() -> None:
    # Arrange
    text = (
        'import { signal, linkedSignal } from "@angular/core";\n'
        "const source = signal(0);\n"
        "const linked = linkedSignal(() => source());\n"
        "linked.set(5);\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "app.component.ts")

    # Assert
    assert scope is True
    assert label == "angular-signals"


def test_angular_resource_recognized() -> None:
    # Arrange
    text = (
        'import { resource } from "@angular/core";\n'
        "const userResource = resource({ loader: () => fetchUser() });\n"
        "userResource.reload();\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "user.component.ts")

    # Assert
    assert scope is True
    assert label == "angular-signals"


def test_signal_filename_allowlisted() -> None:
    # Arrange
    file_path = "src/state/user.signal.ts"

    # Act
    result = is_state_mgmt_filename(file_path)

    # Assert
    assert result is True


def test_preact_useSignal_react_variant() -> None:
    # Arrange
    text = (
        'import { useSignal } from "@preact/signals-react";\n'
        "function Counter() {\n"
        "  const count = useSignal(0);\n"
        "  return <button onClick={() => count.value++}>{count}</button>;\n"
        "}\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "Counter.tsx")

    # Assert
    assert scope is True
    assert label == "preact-signals"


def test_solid_resource_does_not_flag_helpers() -> None:
    # Arrange
    text = (
        'import { createResource, createMemo } from "solid-js";\n'
        "const [data] = createResource(fetchUser);\n"
        "const total = createMemo(() => items().length);\n"
    )

    # Act
    _scope, label = is_in_state_mgmt_scope(text, "comp.tsx")

    # Assert
    assert label not in ("tc39-signals", "angular-signals")


def test_combined_imports_picks_first_match() -> None:
    # Arrange
    text = (
        'import { computed } from "@angular/core";\n'
        'import { signal } from "@preact/signals";\n'
        "const a = computed(() => 0);\n"
        "const b = signal(0);\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "x.ts")

    # Assert
    assert scope is True
    assert label in ("angular-signals", "preact-signals")


def test_qwik_filename_pattern_match() -> None:
    # Arrange
    file_path = "src/routes/products.qwik.tsx"

    # Act
    result = is_state_mgmt_filename(file_path)

    # Assert
    assert result is True


def test_qwik_useStore_var_decl_collected() -> None:
    # Arrange
    text = (
        'import { useStore } from "@builder.io/qwik";\n'
        "const state = useStore({ count: 0, items: [] });\n"
        "state.count = 5;\n"
    )

    # Act
    receivers = collect_state_mgmt_receivers(text, "comp.tsx")

    # Assert
    assert "qwik-signals" in receivers


def test_preact_compute_var_decl_collected() -> None:
    # Arrange
    text = (
        'import { signal, computed } from "@preact/signals";\n'
        "const count = signal(0);\n"
        "const double = computed(() => count.value * 2);\n"
    )

    # Act
    receivers = collect_state_mgmt_receivers(text, "x.ts")

    # Assert
    assert "preact-signals" in receivers
    assert receivers["preact-signals"] >= {"count", "double"}


def test_tc39_signal_computed_var_decl_collected() -> None:
    # Arrange
    text = (
        'import { Signal } from "signal-polyfill";\n'
        "const counter = new Signal.State(0);\n"
        "const double = new Signal.Computed(() => counter.get() * 2);\n"
    )

    # Act
    receivers = collect_state_mgmt_receivers(text, "x.ts")

    # Assert
    assert "tc39-signals" in receivers
    assert receivers["tc39-signals"] >= {"counter", "double"}


def test_effect_ts_subscription_ref_recognized() -> None:
    # Arrange
    text = (
        'import { SubscriptionRef } from "effect";\n'
        "const sub = SubscriptionRef.make(0);\n"
        "SubscriptionRef.set(sub, 5);\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "sub.ts")

    # Assert
    assert scope is True
    assert label == "effect-ts"


def test_svelte_state_raw_receivers_collected() -> None:
    # Arrange
    text = (
        "let items = $state.raw([1, 2, 3]);\n"
        "let active = $state(true);\n"
        "let tags: string[] = $state.raw<string[]>([]);\n"
    )

    # Act
    raw_receivers = collect_svelte_state_raw_receivers(text)

    # Assert
    assert raw_receivers == {"items", "tags"}


def test_svelte_state_raw_empty_when_no_raw_decl() -> None:
    # Arrange
    text = "let count = $state(0);\nlet doubled = $derived(count * 2);\n"

    # Act
    raw_receivers = collect_svelte_state_raw_receivers(text)

    # Assert
    assert raw_receivers == set()
