from __future__ import annotations

import pytest

from conftest import make_write_payload


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
    assert "[svelte.derived-reassign]" in stderr


VUE_SHALLOW_READONLY_BLOCKED_FIXTURES: list[tuple[str, str]] = [
    (
        "vue-shallow-readonly-nested-dot",
        """import { shallowReadonly } from "vue";
const state = shallowReadonly({ user: { name: "a" } });
function bad() {
  state.user.name = "b";
}
""",
    ),
    (
        "vue-shallow-readonly-nested-compound",
        """import { shallowReadonly } from "vue";
const state = shallowReadonly({ counter: { value: 0 } });
function bump() {
  state.counter.value += 1;
}
""",
    ),
    (
        "vue-shallow-readonly-nested-bracket",
        """import { shallowReadonly } from "vue";
const cfg = shallowReadonly({ map: { a: 1 } });
function bad(key) {
  cfg.map[key] = 2;
}
""",
    ),
]


@pytest.mark.parametrize(("label", "snippet"), VUE_SHALLOW_READONLY_BLOCKED_FIXTURES)
def test_vue_shallow_readonly_nested_writes_blocked(run_hook, label, snippet):
    # Arrange
    payload = make_write_payload("/repo/src/store.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{label}: nested write on shallowReadonly should block\n{stderr}"
    assert "[vue.shallow-readonly-nested-write]" in stderr


def test_pinia_patch_callback_allows_state_mutation(run_hook):
    # Arrange
    snippet = """import { defineStore } from "pinia";
const useCounter = defineStore("counter", {
  state: () => ({ count: 0 }),
});
function bump() {
  const counter = useCounter();
  counter.$patch((state) => {
    state.count += 1;
  });
}
"""
    payload = make_write_payload("/repo/src/store.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""


def test_pinia_patch_arrow_single_param_allowed(run_hook):
    # Arrange
    snippet = """import { defineStore } from "pinia";
const useCounter = defineStore("counter", {
  state: () => ({ items: [] }),
});
function add(item) {
  const c = useCounter();
  c.$patch(state => {
    state.items.push(item);
  });
}
"""
    payload = make_write_payload("/repo/src/store.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""


XSTATE_NON_ASSIGN_BLOCKED_FIXTURES: list[tuple[str, str]] = [
    (
        "xstate-direct-context-write-in-action",
        """import { setup } from "xstate";
const machine = setup({
  actions: {
    increment: ({ context }) => {
      context.count = context.count + 1;
    },
  },
}).createMachine({ context: { count: 0 } });
""",
    ),
    (
        "xstate-direct-context-write-compound",
        """import { setup } from "xstate";
const machine = setup({
  actions: {
    bump: ({ context }) => {
      context.count += 1;
    },
  },
}).createMachine({ context: { count: 0 } });
""",
    ),
]


@pytest.mark.parametrize(("label", "snippet"), XSTATE_NON_ASSIGN_BLOCKED_FIXTURES)
def test_xstate_non_assign_context_write_blocked(run_hook, label, snippet):
    # Arrange
    payload = make_write_payload("/repo/src/machine.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{label}: direct context write should block\n{stderr}"
    assert "[xstate.non-assign-context-write]" in stderr


def test_xstate_assign_callback_context_write_allowed(run_hook):
    # Arrange
    snippet = """import { setup, assign } from "xstate";
const machine = setup({
  actions: {
    increment: assign(({ context }) => ({
      count: context.count + 1,
    })),
  },
}).createMachine({ context: { count: 0 } });
"""
    payload = make_write_payload("/repo/src/machine.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""
