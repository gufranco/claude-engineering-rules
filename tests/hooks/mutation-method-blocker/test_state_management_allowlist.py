"""State-management library allowlist coverage.

Item 123 of the plan. Confirms that mutations inside Immer `produce`,
Mutative `create`, Redux Toolkit `createSlice` reducers and `extraReducers`,
Pinia `defineStore`, Vuex `mutations`, MobX actions, Zustand `set(produce(...))`,
and Yjs CRDT types are auto-allowed.

The allowlist is critical to avoid punishing canonical state-management
patterns. This file validates each library scope individually so a regression
in one detector does not silently break the others.
"""

from __future__ import annotations

import pytest

from conftest import make_write_payload

IMMER_FIXTURES: list[tuple[str, str]] = [
    (
        "immer-produce-arrow",
        """import { produce } from 'immer';
export const reducer = (state, action) => produce(state, (draft) => {
  draft.count = state.count + 1;
  draft.items.push(action.item);
  draft.flags.active = true;
});
""",
    ),
    (
        "immer-produce-fn",
        """import { produce } from 'immer';
export function next(state, action) {
  return produce(state, function (draft) {
    draft.list.push(action.item);
    draft.totals.sum += action.amount;
  });
}
""",
    ),
]

MUTATIVE_FIXTURES: list[tuple[str, str]] = [
    (
        "mutative-create-arrow",
        """import { create } from 'mutative';
export const next = (state) => create(state, (draft) => {
  draft.list.push(1);
  draft.flags.ready = true;
});
""",
    ),
]

REDUX_TOOLKIT_FIXTURES: list[tuple[str, str]] = [
    (
        "redux-toolkit-createSlice",
        """import { createSlice } from '@reduxjs/toolkit';
const slice = createSlice({
  name: 'cart',
  initialState: { items: [] },
  reducers: {
    addItem(state, action) {
      state.items.push(action.payload);
    },
    setReady(state) {
      state.ready = true;
    },
  },
});
""",
    ),
    (
        "redux-toolkit-extraReducers-builder",
        """import { createSlice } from '@reduxjs/toolkit';
const slice = createSlice({
  name: 'orders',
  initialState: { list: [] },
  reducers: {},
  extraReducers: (builder) => {
    builder.addCase(fetched, (state, action) => {
      state.list.push(action.payload);
    });
    builder.addMatcher(matcher, (state) => {
      state.ready = true;
    });
  },
});
""",
    ),
]

PINIA_FIXTURES: list[tuple[str, str]] = [
    (
        "pinia-defineStore",
        """import { defineStore } from 'pinia';
export const useCart = defineStore('cart', {
  state: () => ({ items: [] }),
  actions: {
    add(item) {
      this.items.push(item);
      this.lastAdded = item;
    },
  },
});
""",
    ),
]

VUEX_FIXTURES: list[tuple[str, str]] = [
    (
        "vuex-mutations-block",
        """const store = new Vuex.Store({
  state: { count: 0 },
  mutations: {
    increment(state) {
      state.count += 1;
    },
  },
});
""",
    ),
]

MOBX_FIXTURES: list[tuple[str, str]] = [
    (
        "mobx-runInAction",
        """import { runInAction } from 'mobx';
runInAction(() => {
  store.count += 1;
  store.items.push(value);
});
""",
    ),
    (
        "mobx-action-decorator",
        """class Counter {
  @action
  increment() {
    this.count += 1;
  }
}
""",
    ),
]

ZUSTAND_FIXTURES: list[tuple[str, str]] = [
    (
        "zustand-set-produce",
        """import { create } from 'zustand';
import { produce } from 'immer';
export const useStore = create((set) => ({
  count: 0,
  bump: () => set(produce((draft) => {
    draft.count += 1;
  })),
}));
""",
    ),
]

YJS_FIXTURES: list[tuple[str, str]] = [
    (
        "yjs-array-push",
        """const yArr = new Y.Array();
yArr.push(['x']);
yArr.delete(0);
""",
    ),
    (
        "yjs-map-set",
        """const yMap = new Y.Map();
yMap.set('k', 'v');
yMap.delete('k');
""",
    ),
]

VALTIO_FIXTURES: list[tuple[str, str]] = [
    (
        "valtio-proxy-assignment",
        """import { proxy } from 'valtio';
const state = proxy({ count: 0, items: [] });
state.count = state.count + 1;
state.items.push('a');
""",
    ),
    (
        "valtio-proxyMap-set",
        """import { proxyMap } from 'valtio/utils';
const m = proxyMap();
m.set('k', 'v');
m.delete('k');
""",
    ),
]

JOTAI_FIXTURES: list[tuple[str, str]] = [
    (
        "jotai-useSetAtom-update",
        """import { atom, useSetAtom } from 'jotai';
const countAtom = atom(0);
function Component() {
  const setCount = useSetAtom(countAtom);
  setCount((c) => c + 1);
}
""",
    ),
    (
        "jotai-atomWithReducer",
        """import { atomWithReducer } from 'jotai/utils';
const counter = atomWithReducer(0, (state, action) => {
  state.count += 1;
  return state;
});
""",
    ),
]

RECOIL_FIXTURES: list[tuple[str, str]] = [
    (
        "recoil-useRecoilState",
        """import { atom, useRecoilState } from 'recoil';
const counterState = atom({ key: 'counter', default: 0 });
function Counter() {
  const [count, setCount] = useRecoilState(counterState);
  setCount(count + 1);
}
""",
    ),
]

XSTATE_FIXTURES: list[tuple[str, str]] = [
    (
        "xstate-v5-setup-assign",
        """import { setup, assign } from 'xstate';
const machine = setup({}).createMachine({
  context: { count: 0 },
  on: {
    INC: { actions: assign({ count: ({ context }) => context.count + 1 }) },
  },
});
""",
    ),
    (
        "xstate-createMachine-assign",
        """import { createMachine, assign } from 'xstate';
const machine = createMachine({
  context: { items: [] },
  on: {
    ADD: { actions: assign({ items: ({ context, event }) => [...context.items, event.item] }) },
  },
});
""",
    ),
]

SOLID_STORE_FIXTURES: list[tuple[str, str]] = [
    (
        "solid-createStore-setStore",
        """import { createStore } from 'solid-js/store';
const [state, setStore] = createStore({ count: 0, items: [] });
setStore('count', (c) => c + 1);
state.items.push('x');
""",
    ),
    (
        "solid-createMutable",
        """import { createMutable } from 'solid-js/store';
const state = createMutable({ count: 0 });
state.count = state.count + 1;
""",
    ),
]

NANOSTORES_FIXTURES: list[tuple[str, str]] = [
    (
        "nanostores-atom-set",
        """import { atom } from 'nanostores';
export const $count = atom(0);
$count.set($count.get() + 1);
""",
    ),
    (
        "nanostores-map-setKey",
        """import { map } from 'nanostores';
export const $user = map({ name: '', age: 0 });
$user.setKey('name', 'a');
""",
    ),
]

LEGENDAPP_FIXTURES: list[tuple[str, str]] = [
    (
        "legendapp-observable-set",
        """import { observable } from '@legendapp/state';
const state$ = observable({ count: 0, items: [] });
state$.count.set(1);
state$.items.push('a');
""",
    ),
]

TANSTACK_STORE_FIXTURES: list[tuple[str, str]] = [
    (
        "tanstack-store-setState",
        """import { Store } from '@tanstack/store';
const store = new Store({ count: 0 });
store.setState((prev) => ({ count: prev.count + 1 }));
""",
    ),
]

EFFECT_DATA_FIXTURES: list[tuple[str, str]] = [
    (
        "effect-data-tagged",
        """import { Data } from 'effect';
class Increment extends Data.TaggedClass('Increment')<{ amount: number }> {}
const e = new Increment({ amount: 1 });
""",
    ),
    (
        "effect-data-struct",
        """import { Data } from 'effect';
const Point = Data.struct({ x: 0, y: 0 });
""",
    ),
]

VUE_READONLY_FIXTURES: list[tuple[str, str]] = [
    (
        "vue-readonly-reactive",
        """import { readonly, reactive } from 'vue';
const internal = reactive({ count: 0 });
const view = readonly(internal);
internal.count = internal.count + 1;
""",
    ),
    (
        "vue-shallowReadonly-ref",
        """import { shallowReadonly, ref } from 'vue';
const internal = ref({ items: [] });
const view = shallowReadonly(internal);
internal.value.items.push('a');
""",
    ),
]

SVELTE_RUNES_FIXTURES: list[tuple[str, str]] = [
    (
        "svelte5-state-rune",
        """let count = $state(0);
let items = $state<string[]>([]);
function bump() {
  count = count + 1;
  items.push('a');
}
""",
    ),
    (
        "svelte5-derived-rune",
        """let total = $state(0);
let double = $derived(total * 2);
function inc() {
  total += 1;
}
""",
    ),
]

STATE_MGMT_FILENAME_FIXTURES: list[tuple[str, str, str]] = [
    (
        "filename-slice",
        "/repo/src/features/cart/cartSlice.ts",
        """const initialState = { items: [] };
function reducer(state, action) {
  state.items.push(action.payload);
  return state;
}
""",
    ),
    (
        "filename-store",
        "/repo/src/store/userStore.ts",
        """function setUser(state, user) {
  state.user = user;
}
""",
    ),
    (
        "filename-reducer",
        "/repo/src/state/orders.reducer.ts",
        """function reducer(state, action) {
  state.list.push(action.payload);
  return state;
}
""",
    ),
    (
        "filename-machine",
        "/repo/src/machines/auth.machine.ts",
        """function transition(state, event) {
  state.count += 1;
  return state;
}
""",
    ),
    (
        "filename-atom",
        "/repo/src/state/counter.atom.ts",
        """const state = { count: 0 };
state.count = state.count + 1;
""",
    ),
    (
        "filename-proxy",
        "/repo/src/state/cart.proxy.ts",
        """const state = { items: [] };
state.items.push('x');
""",
    ),
    (
        "filename-valtio",
        "/repo/src/store/cart.valtio.ts",
        """const state = { items: [] };
state.items.push('x');
""",
    ),
    (
        "filename-svelte",
        "/repo/src/lib/Counter.svelte",
        """let count = 0;
function bump() {
  count += 1;
}
""",
    ),
    (
        "filename-svelte-runes-ts",
        "/repo/src/lib/state.svelte.ts",
        """let total = 0;
function inc() {
  total += 1;
}
""",
    ),
]


ALL_ALLOWED = (
    IMMER_FIXTURES
    + MUTATIVE_FIXTURES
    + REDUX_TOOLKIT_FIXTURES
    + PINIA_FIXTURES
    + VUEX_FIXTURES
    + MOBX_FIXTURES
    + ZUSTAND_FIXTURES
    + YJS_FIXTURES
    + VALTIO_FIXTURES
    + JOTAI_FIXTURES
    + RECOIL_FIXTURES
    + XSTATE_FIXTURES
    + SOLID_STORE_FIXTURES
    + NANOSTORES_FIXTURES
    + LEGENDAPP_FIXTURES
    + TANSTACK_STORE_FIXTURES
    + EFFECT_DATA_FIXTURES
    + VUE_READONLY_FIXTURES
)


@pytest.mark.parametrize(("label", "snippet"), ALL_ALLOWED)
def test_state_management_scope_allowed(run_hook, label, snippet):
    # Arrange
    payload = make_write_payload("/repo/src/state.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"{label}: unexpected block\n{stderr}"


@pytest.mark.parametrize(("label", "snippet"), SVELTE_RUNES_FIXTURES)
def test_svelte_runes_scope_allowed(run_hook, label, snippet):
    # Arrange
    payload = make_write_payload("/repo/src/lib/Counter.svelte.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"{label}: unexpected block\n{stderr}"


@pytest.mark.parametrize(("label", "path", "snippet"), STATE_MGMT_FILENAME_FIXTURES)
def test_state_management_filename_allowed(run_hook, label, path, snippet):
    # Arrange
    payload = make_write_payload(path, snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"{label}: unexpected block\n{stderr}"


STATE_MGMT_MISUSE_FIXTURES: list[tuple[str, str]] = [
    (
        "valtio-import-but-mutate-untracked",
        """import { proxy } from 'valtio';
const trackedState = proxy({ count: 0 });
const items = [];
items.push('x');
""",
    ),
    (
        "vue-reactive-import-but-mutate-untracked",
        """import { reactive } from 'vue';
const trackedState = reactive({ count: 0 });
const list = [];
list.push('x');
""",
    ),
    (
        "solid-store-import-but-mutate-untracked",
        """import { createStore } from 'solid-js/store';
const [tracked, setStore] = createStore({ count: 0 });
const items = [];
items.push('x');
""",
    ),
    (
        "nanostores-import-but-mutate-untracked",
        """import { atom } from 'nanostores';
const $tracked = atom(0);
const arr = [];
arr.push(1);
""",
    ),
    (
        "legendapp-import-but-mutate-untracked",
        """import { observable } from '@legendapp/state';
const tracked$ = observable({ count: 0 });
const items = [];
items.push('x');
""",
    ),
]


@pytest.mark.parametrize(("label", "snippet"), STATE_MGMT_MISUSE_FIXTURES)
def test_state_management_misuse_still_blocked(run_hook, label, snippet):
    # Arrange
    payload = make_write_payload("/repo/src/state.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{label}: should have been blocked\n{stderr}"


SVELTE_STATE_RAW_BLOCKED_FIXTURES: list[tuple[str, str]] = [
    (
        "svelte-state-raw-push",
        """let items = $state.raw<string[]>([]);
function add(x) {
  items.push(x);
}
""",
    ),
    (
        "svelte-state-raw-sort",
        """let list = $state.raw([3, 1, 2]);
function sortAsc() {
  list.sort();
}
""",
    ),
]


@pytest.mark.parametrize(("label", "snippet"), SVELTE_STATE_RAW_BLOCKED_FIXTURES)
def test_svelte_state_raw_mutations_blocked(run_hook, label, snippet):
    # Arrange
    payload = make_write_payload("/repo/src/lib/store.svelte.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{label}: $state.raw mutation should block\n{stderr}"


SVELTE_DERIVED_REASSIGN_FIXTURES: list[tuple[str, str]] = [
    (
        "svelte-derived-plain-reassign",
        """let total = $state(0);
let double = $derived(total * 2);
function bad() {
  double = 999;
}
""",
    ),
    (
        "svelte-derived-compound-reassign",
        """let count = $state(0);
let triple = $derived(count * 3);
function bump() {
  triple += 1;
}
""",
    ),
]


@pytest.mark.parametrize(("label", "snippet"), SVELTE_DERIVED_REASSIGN_FIXTURES)
def test_svelte_derived_reassignment_blocked(run_hook, label, snippet):
    # Arrange
    payload = make_write_payload("/repo/src/lib/comp.svelte.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{label}: $derived reassignment should block\n{stderr}"
    assert "svelte.derived-reassign" in stderr or "MMB098" in stderr
