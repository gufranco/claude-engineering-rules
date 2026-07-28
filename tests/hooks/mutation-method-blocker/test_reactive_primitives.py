"""Phase 36 integration tests: modern reactive primitives.

Verifies that the allowlist recognizes Angular signals, Qwik signals, Preact
signals, React 19 useFormState/useActionState, TC39 Signals proposal, Solid
stores/resources, Effect-TS Ref and Effect.gen, and fp-ts pipe/flow patterns.

For each framework, two assertions hold:

  1. POSITIVE: when the framework's import is present and the call matches the
     framework's idiomatic usage, the mutation surface is allowlisted.
  2. NEGATIVE: when the same mutation pattern appears without the import, the
     allowlist does NOT recognize the scope. The hook may still allow via
     other paths (filename match, framework receiver list); the test asserts
     only that the framework-specific signal does not light up.
"""

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


def test_angular_signals_positive() -> None:
    text = (
        'import { signal, computed } from "@angular/core";\n'
        "const count = signal(0);\n"
        "const double = computed(() => count() * 2);\n"
        "count.set(5);\n"
        "count.update(v => v + 1);\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "app.component.ts")
    receivers = collect_state_mgmt_receivers(text, "app.component.ts")

    assert scope is True
    assert label == "angular-signals"
    assert "angular-signals" in receivers
    assert "count" in receivers["angular-signals"]


def test_angular_signals_negative_without_import() -> None:
    text = "const count = signal(0);\ncount.set(5);\n"

    scope, label = is_in_state_mgmt_scope(text, "plain.ts")
    receivers = collect_state_mgmt_receivers(text, "plain.ts")

    assert label != "angular-signals"
    assert "angular-signals" not in receivers


def test_angular_component_filename_allowlisted() -> None:
    assert is_state_mgmt_filename("src/app/counter.component.ts") is True
    assert is_state_mgmt_filename("src/app/data.service.ts") is True


def test_qwik_signals_positive() -> None:
    text = (
        'import { useSignal, useStore } from "@builder.io/qwik";\n'
        "const count = useSignal(0);\n"
        "const state = useStore({ items: [] });\n"
        "count.value = 5;\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "counter.tsx")
    receivers = collect_state_mgmt_receivers(text, "counter.tsx")

    assert scope is True
    assert label == "qwik-signals"
    assert "count" in receivers["qwik-signals"]


def test_qwik_signals_negative_without_import() -> None:
    text = "const count = useSignal(0);\ncount.value = 5;\n"

    scope, label = is_in_state_mgmt_scope(text, "comp.tsx")

    assert label != "qwik-signals"


def test_qwik_filename_allowlisted() -> None:
    assert is_state_mgmt_filename("src/components/counter.qwik.tsx") is True


def test_preact_signals_positive() -> None:
    text = (
        'import { signal, computed } from "@preact/signals";\n'
        "const count = signal(0);\n"
        "count.value = 5;\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "app.tsx")
    receivers = collect_state_mgmt_receivers(text, "app.tsx")

    assert scope is True
    assert label == "preact-signals"
    assert "count" in receivers["preact-signals"]


def test_preact_signals_core_positive() -> None:
    text = (
        'import { signal, batch } from "@preact/signals-core";\n'
        "const x = signal(0);\n"
        "batch(() => { x.value = 1; });\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "core.ts")

    assert scope is True
    assert label == "preact-signals"


def test_preact_signals_react_variant() -> None:
    text = (
        'import { useSignal } from "@preact/signals-react";\n'
        "const count = useSignal(0);\n"
        "count.value = 5;\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "comp.tsx")

    assert scope is True
    assert label == "preact-signals"


def test_preact_signals_negative_without_import() -> None:
    text = "const count = signal(0);\ncount.value = 5;\n"

    scope, label = is_in_state_mgmt_scope(text, "plain.ts")

    assert label != "preact-signals"


def test_react_19_useactionstate_recognized() -> None:
    text = (
        'import { useActionState } from "react";\n'
        "const [state, formAction] = useActionState(reducer, initial);\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "form.tsx")

    assert scope is True
    assert label == "react-19-state-hooks"


def test_react_19_useformstate_recognized() -> None:
    text = (
        'import { useFormState } from "react-dom";\n'
        "const [state, action] = useFormState(submit, null);\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "form.tsx")

    assert scope is True
    assert label == "react-19-state-hooks"


def test_react_19_useoptimistic_recognized() -> None:
    text = (
        'import { useOptimistic } from "react";\n'
        "const [optimistic, addOptimistic] = useOptimistic(items);\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "list.tsx")

    assert scope is True
    assert label == "react-19-state-hooks"


def test_react_usereducer_body_recognized() -> None:
    text = (
        'import { useReducer } from "react";\n'
        "const [state, dispatch] = useReducer(reducer, initial);\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "comp.tsx")

    assert scope is True
    assert label == "react-19-state-hooks"


def test_react_server_action_directive_recognized() -> None:
    text = (
        '"use server";\n'
        'import { db } from "@/lib/db";\n'
        "async function createPost(formData) {\n"
        "  return db.post.create({ data: { ... } });\n"
        "}\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "actions.ts")

    assert scope is True
    assert label == "react-server-action"


def test_react_no_directive_does_not_flag_server_action() -> None:
    text = (
        'import { db } from "@/lib/db";\n'
        "async function createPost(formData) {\n"
        "  return db.post.create({ data: { ... } });\n"
        "}\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "actions.ts")

    assert label != "react-server-action"


def test_solid_store_with_produce_recognized() -> None:
    text = (
        'import { createStore, produce, unwrap } from "solid-js/store";\n'
        "const [state, setState] = createStore({ items: [] });\n"
        "setState(produce(s => { s.items.push(item); }));\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "comp.tsx")

    assert scope is True
    assert label in ("solid-produce", "solid-store")


def test_solid_reconcile_distinct_from_produce() -> None:
    text = (
        'import { createStore, reconcile } from "solid-js/store";\n'
        "const [state, setState] = createStore({ items: [] });\n"
        "setState(reconcile(nextFromServer));\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "comp.tsx")

    assert scope is True
    assert label == "solid-reconcile"


def test_solid_produce_label_when_both_present() -> None:
    text = (
        'import { createStore, produce, reconcile } from "solid-js/store";\n'
        "const [state, setState] = createStore({ items: [] });\n"
        "setState(produce(s => { s.items.push(item); }));\n"
        "setState(reconcile(nextFromServer));\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "comp.tsx")

    assert scope is True
    assert label == "solid-produce"


def test_tc39_signals_proposal_recognized() -> None:
    text = (
        'import { Signal } from "signal-polyfill";\n'
        "const counter = new Signal.State(0);\n"
        "counter.set(5);\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "store.ts")
    receivers = collect_state_mgmt_receivers(text, "store.ts")

    assert scope is True
    assert label == "tc39-signals"
    assert "counter" in receivers["tc39-signals"]


def test_tc39_signals_negative_without_import() -> None:
    text = "const counter = new Signal.State(0);\ncounter.set(5);\n"

    scope, label = is_in_state_mgmt_scope(text, "plain.ts")

    assert label != "tc39-signals"


def test_effect_ts_gen_recognized() -> None:
    text = (
        'import { Effect, Ref } from "effect";\n'
        "const program = Effect.gen(function*() {\n"
        "  const ref = yield* Ref.make(0);\n"
        "  yield* Ref.update(ref, n => n + 1);\n"
        "});\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "program.ts")

    assert scope is True
    assert label == "effect-ts"


def test_effect_ts_ref_recognized() -> None:
    text = 'import { Ref } from "effect";\nconst ref = Ref.make(0);\nRef.set(ref, 5);\n'

    scope, label = is_in_state_mgmt_scope(text, "ref.ts")

    assert scope is True
    assert label == "effect-ts"


def test_effect_ts_negative_without_import() -> None:
    text = "const ref = Ref.make(0);\nRef.set(ref, 5);\n"

    scope, label = is_in_state_mgmt_scope(text, "plain.ts")

    assert label != "effect-ts"


def test_effect_filename_allowlisted() -> None:
    assert is_state_mgmt_filename("src/programs/orders.effect.ts") is True


def test_angular_linkedsignal_recognized() -> None:
    text = (
        'import { signal, linkedSignal } from "@angular/core";\n'
        "const source = signal(0);\n"
        "const linked = linkedSignal(() => source());\n"
        "linked.set(5);\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "app.component.ts")

    assert scope is True
    assert label == "angular-signals"


def test_angular_resource_recognized() -> None:
    text = (
        'import { resource } from "@angular/core";\n'
        "const userResource = resource({ loader: () => fetchUser() });\n"
        "userResource.reload();\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "user.component.ts")

    assert scope is True
    assert label == "angular-signals"


def test_signal_filename_allowlisted() -> None:
    assert is_state_mgmt_filename("src/state/user.signal.ts") is True


def test_preact_useSignal_react_variant() -> None:
    text = (
        'import { useSignal } from "@preact/signals-react";\n'
        "function Counter() {\n"
        "  const count = useSignal(0);\n"
        "  return <button onClick={() => count.value++}>{count}</button>;\n"
        "}\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "Counter.tsx")

    assert scope is True
    assert label == "preact-signals"


def test_solid_resource_does_not_flag_helpers() -> None:
    text = (
        'import { createResource, createMemo } from "solid-js";\n'
        "const [data] = createResource(fetchUser);\n"
        "const total = createMemo(() => items().length);\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "comp.tsx")

    if scope is True:
        assert label != "tc39-signals"
        assert label != "angular-signals"


def test_combined_imports_picks_first_match() -> None:
    text = (
        'import { computed } from "@angular/core";\n'
        'import { signal } from "@preact/signals";\n'
        "const a = computed(() => 0);\n"
        "const b = signal(0);\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "x.ts")

    assert scope is True
    assert label in ("angular-signals", "preact-signals")


def test_qwik_filename_pattern_match() -> None:
    assert is_state_mgmt_filename("src/routes/products.qwik.tsx") is True


def test_qwik_useStore_var_decl_collected() -> None:
    text = (
        'import { useStore } from "@builder.io/qwik";\n'
        "const state = useStore({ count: 0, items: [] });\n"
        "state.count = 5;\n"
    )

    receivers = collect_state_mgmt_receivers(text, "comp.tsx")

    assert "qwik-signals" in receivers


def test_preact_compute_var_decl_collected() -> None:
    text = (
        'import { signal, computed } from "@preact/signals";\n'
        "const count = signal(0);\n"
        "const double = computed(() => count.value * 2);\n"
    )

    receivers = collect_state_mgmt_receivers(text, "x.ts")

    assert "preact-signals" in receivers
    assert receivers["preact-signals"] >= {"count", "double"}


def test_tc39_signal_computed_var_decl_collected() -> None:
    text = (
        'import { Signal } from "signal-polyfill";\n'
        "const counter = new Signal.State(0);\n"
        "const double = new Signal.Computed(() => counter.get() * 2);\n"
    )

    receivers = collect_state_mgmt_receivers(text, "x.ts")

    assert "tc39-signals" in receivers
    assert receivers["tc39-signals"] >= {"counter", "double"}


def test_effect_ts_subscription_ref_recognized() -> None:
    text = (
        'import { SubscriptionRef } from "effect";\n'
        "const sub = SubscriptionRef.make(0);\n"
        "SubscriptionRef.set(sub, 5);\n"
    )

    scope, label = is_in_state_mgmt_scope(text, "sub.ts")

    assert scope is True
    assert label == "effect-ts"


def test_svelte_state_raw_receivers_collected() -> None:
    text = (
        "let items = $state.raw([1, 2, 3]);\n"
        "let active = $state(true);\n"
        "let tags: string[] = $state.raw<string[]>([]);\n"
    )

    raw_receivers = collect_svelte_state_raw_receivers(text)

    assert raw_receivers == {"items", "tags"}


def test_svelte_state_raw_empty_when_no_raw_decl() -> None:
    text = "let count = $state(0);\nlet doubled = $derived(count * 2);\n"

    raw_receivers = collect_svelte_state_raw_receivers(text)

    assert raw_receivers == set()
