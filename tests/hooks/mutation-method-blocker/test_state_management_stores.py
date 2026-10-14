from __future__ import annotations

import pytest

from conftest import FINDING_TAG, make_write_payload


EFFECT_TS_REF_BLOCKED_FIXTURES: list[tuple[str, str]] = [
    (
        "effect-ts-ref-value-assign",
        """import { Effect, Ref } from "effect";
const program = Effect.gen(function* () {
  const ref = yield* Ref.make(0);
  ref.value = 5;
});
""",
    ),
    (
        "effect-ts-subscription-ref-value-assign",
        """import { SubscriptionRef } from "effect";
const ref = SubscriptionRef.make(0);
function bad() {
  ref.value = 5;
}
""",
    ),
]


@pytest.mark.parametrize(("label", "snippet"), EFFECT_TS_REF_BLOCKED_FIXTURES)
def test_effect_ts_ref_value_assign_blocked(run_hook, label, snippet):
    # Arrange
    payload = make_write_payload("/repo/src/program.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{label}: Effect-TS Ref.value assignment should block\n{stderr}"
    assert "[effect-ts.ref-value-assign]" in stderr


def test_effect_ts_ref_set_allowed(run_hook):
    # Arrange
    snippet = """import { Effect, Ref } from "effect";
const program = Effect.gen(function* () {
  const ref = yield* Ref.make(0);
  yield* Ref.set(ref, 5);
});
"""
    payload = make_write_payload("/repo/src/program.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""


NANOSTORES_COMPUTED_BLOCKED_FIXTURES: list[tuple[str, str]] = [
    (
        "nanostores-computed-set",
        """import { atom, computed } from "nanostores";
const a = atom(0);
const doubled = computed(a, (v) => v * 2);
function bad() {
  doubled.set(99);
}
""",
    ),
    (
        "nanostores-computed-setKey",
        """import { map, computed } from "nanostores";
const m = map({ a: 1 });
const view = computed(m, (s) => s);
function bad() {
  view.setKey("a", 9);
}
""",
    ),
]


@pytest.mark.parametrize(("label", "snippet"), NANOSTORES_COMPUTED_BLOCKED_FIXTURES)
def test_nanostores_computed_write_blocked(run_hook, label, snippet):
    # Arrange
    payload = make_write_payload("/repo/src/store.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{label}: nanostores computed write should block\n{stderr}"
    assert "[nanostores.computed-write]" in stderr


def test_nanostores_atom_set_allowed(run_hook):
    # Arrange
    snippet = """import { atom } from "nanostores";
const counter = atom(0);
function bump() {
  counter.set(counter.get() + 1);
}
"""
    payload = make_write_payload("/repo/src/store.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""


TANSTACK_STORE_BLOCKED_FIXTURES: list[tuple[str, str]] = [
    (
        "tanstack-state-direct-write",
        """import { Store } from "@tanstack/store";
const store = new Store({ count: 0 });
function bad() {
  store.state.count = 1;
}
""",
    ),
    (
        "tanstack-state-compound",
        """import { createStore } from "@tanstack/react-store";
const store = createStore({ count: 0 });
function bump() {
  store.state.count += 1;
}
""",
    ),
]


@pytest.mark.parametrize(("label", "snippet"), TANSTACK_STORE_BLOCKED_FIXTURES)
def test_tanstack_store_state_direct_write_blocked(run_hook, label, snippet):
    # Arrange
    payload = make_write_payload("/repo/src/store.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, (
        f"{label}: TanStack store.state direct write should block\n{stderr}"
    )
    assert "[tanstack.store-state-write]" in stderr


def test_tanstack_setstate_callback_allowed(run_hook):
    # Arrange
    snippet = """import { Store } from "@tanstack/store";
const store = new Store({ count: 0 });
function bump() {
  store.setState((prev) => ({ count: prev.count + 1 }));
}
"""
    payload = make_write_payload("/repo/src/store.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""


def test_vue_shallow_readonly_top_level_not_flagged_by_new_detector(run_hook):
    # Arrange
    snippet = """import { shallowReadonly } from "vue";
const state = shallowReadonly({ count: 0 });
function bad() {
  state.count = 1;
}
"""
    payload = make_write_payload("/repo/src/store.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""


MOBX_ENFORCE_ACTIONS_BLOCKED_FIXTURES: list[tuple[str, str]] = [
    (
        "mobx-observable-direct-assign",
        """import { observable, configure } from "mobx";
configure({ enforceActions: "always" });
const store = observable({ count: 0 });
function bump() {
  store.count = 1;
}
""",
    ),
    (
        "mobx-makeAutoObservable-compound-assign",
        """import { makeAutoObservable, configure } from "mobx";
configure({ enforceActions: 'always' });
const counter = makeAutoObservable({ count: 0 });
function bump() {
  counter.count += 1;
}
""",
    ),
    (
        "mobx-makeObservable-increment",
        """import { makeObservable, configure } from "mobx";
configure({ enforceActions: "always" });
const tracker = makeObservable({ hits: 0 });
function bump() {
  tracker.hits++;
}
""",
    ),
]


@pytest.mark.parametrize(
    "name,snippet", MOBX_ENFORCE_ACTIONS_BLOCKED_FIXTURES, ids=lambda v: v
)
def test_mobx_observable_outside_action_blocks(name, snippet, run_hook):
    # Arrange
    payload = make_write_payload("/repo/src/store.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "mobx.observable-outside-action" in stderr, (
        f"{name}: detector did not fire\n{stderr}"
    )


def test_mobx_runInAction_wrapped_allowed(run_hook):
    # Arrange
    snippet = """import { observable, runInAction, configure } from "mobx";
configure({ enforceActions: "always" });
const store = observable({ count: 0 });
function bump() {
  runInAction(() => {
    store.count = 1;
  });
}
"""
    payload = make_write_payload("/repo/src/store.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""


def test_mobx_without_enforce_actions_skipped(run_hook):
    # Arrange
    snippet = """import { observable } from "mobx";
const store = observable({ count: 0 });
function bump() {
  store.count = 1;
}
"""
    payload = make_write_payload("/repo/src/store.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""


YJS_OUTSIDE_TRANSACT_BLOCKED_FIXTURES: list[tuple[str, str]] = [
    (
        "yjs-map-set-outside-transact",
        """import * as Y from "yjs";
const yMap = new Y.Map();
function bump() {
  yMap.set("k", "v");
}
""",
    ),
    (
        "yjs-array-push-outside-transact",
        """import * as Y from "yjs";
const yArr = new Y.Array();
function add(item) {
  yArr.push([item]);
}
""",
    ),
    (
        "yjs-text-insert-outside-transact",
        """import * as Y from "yjs";
const yText = new Y.Text();
function write() {
  yText.insert(0, "hello");
}
""",
    ),
    (
        "yjs-doc-getmap-outside-transact",
        """import * as Y from "yjs";
const doc = new Y.Doc();
const yMap = doc.getMap("settings");
function set() {
  yMap.set("theme", "dark");
}
""",
    ),
]


@pytest.mark.parametrize(
    "name,snippet", YJS_OUTSIDE_TRANSACT_BLOCKED_FIXTURES, ids=lambda v: v
)
def test_yjs_mutation_outside_transact_blocks(name, snippet, run_hook):
    # Arrange
    payload = make_write_payload("/repo/src/sync.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "yjs.mutation-outside-transact" in stderr, (
        f"{name}: detector did not fire\n{stderr}"
    )


def test_yjs_mutation_inside_transact_allowed(run_hook):
    # Arrange
    snippet = """import * as Y from "yjs";
const doc = new Y.Doc();
const yMap = doc.getMap("settings");
function update() {
  doc.transact(() => {
    yMap.set("theme", "dark");
    yMap.set("font", "mono");
  });
}
"""
    payload = make_write_payload("/repo/src/sync.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""


def test_yjs_nested_transact_allowed(run_hook):
    # Arrange
    snippet = """import * as Y from "yjs";
const doc = new Y.Doc();
const yArr = new Y.Array();
function bulk(items) {
  doc.transact(() => {
    for (const item of items) {
      yArr.push([item]);
    }
  });
}
"""
    payload = make_write_payload("/repo/src/sync.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""


RECOIL_DEPRECATION_FIXTURES: list[tuple[str, str]] = [
    (
        "recoil-named-import",
        """import { atom } from "recoil";
const counter = atom({ key: "counter", default: 0 });
""",
    ),
    (
        "recoil-namespace-import",
        """import * as Recoil from "recoil";
const a = Recoil.atom({ key: "k", default: 1 });
""",
    ),
    (
        "recoil-multi-import",
        """import { atom, selector, useRecoilState } from 'recoil';
const counter = atom({ key: 'counter', default: 0 });
""",
    ),
]


@pytest.mark.parametrize("name,snippet", RECOIL_DEPRECATION_FIXTURES, ids=lambda v: v)
def test_recoil_import_blocks_with_the_deprecation_pointer(name, snippet, run_hook):
    # Arrange
    payload = make_write_payload("/repo/src/store.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "recoil.deprecation-pointer" in stderr, (
        f"{name}: deprecation pointer not emitted\n{stderr}"
    )


def test_recoil_setter_call_reports_only_the_deprecation_pointer(run_hook):
    # Arrange
    snippet = """import { atom, useRecoilState } from 'recoil';
const counterState = atom({ key: 'counter', default: 0 });
function Counter() {
  const [count, setCount] = useRecoilState(counterState);
  setCount(count + 1);
}
"""
    payload = make_write_payload("/repo/src/state.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert FINDING_TAG.findall(stderr) == ["recoil.deprecation-pointer"]


def test_recoil_deprecation_skipped_without_recoil_import(run_hook):
    # Arrange
    snippet = """import { atom } from "jotai";
const counter = atom(0);
"""
    payload = make_write_payload("/repo/src/store.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""


def test_mobx_action_callback_allowed(run_hook):
    # Arrange
    snippet = """import { observable, action, configure } from "mobx";
configure({ enforceActions: "always" });
const store = observable({ count: 0 });
const bump = action(() => {
  store.count = 1;
});
"""
    payload = make_write_payload("/repo/src/store.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""
