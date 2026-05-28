"""Extra coverage for `scripts/mutation_allowlists.py`.

Targets the early-return guards (empty inputs), the per-library detection
branches in `is_in_state_mgmt_scope`, and the helper functions used by
detectors to dedupe Web API and Temporal owners.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import mutation_allowlists as ma  # noqa: E402


# --------------------------------------------------------------------------- #
# is_dom_receiver / is_dom_assignment edge cases
# --------------------------------------------------------------------------- #


def test_is_dom_receiver_returns_false_for_none() -> None:
    assert ma.is_dom_receiver(None) is False


def test_is_dom_receiver_returns_false_for_empty_string() -> None:
    assert ma.is_dom_receiver("") is False


def test_is_dom_receiver_returns_false_for_whitespace_only() -> None:
    assert ma.is_dom_receiver("   ") is False


def test_is_dom_assignment_returns_false_when_no_signals() -> None:
    # Arrange / Act
    result = ma.is_dom_assignment("notADomReceiver", "someRandomProp")

    # Assert
    assert result is False


# --------------------------------------------------------------------------- #
# Temporal helpers
# --------------------------------------------------------------------------- #


def test_collect_temporal_receivers_returns_empty_for_empty_text() -> None:
    assert ma.collect_temporal_receivers("") == frozenset()


def test_is_temporal_chain_call_returns_false_for_empty_line() -> None:
    assert ma.is_temporal_chain_call("", None, frozenset()) is False


def test_is_temporal_chain_call_matches_chain_pattern_without_owner() -> None:
    # Arrange
    line = "const result = Temporal.Now.instant().add({hours: 1});"

    # Act
    result = ma.is_temporal_chain_call(line, None, frozenset())

    # Assert
    assert result is True


def test_is_temporal_chain_call_returns_false_when_temporal_unrelated() -> None:
    # Arrange
    line = "const x = something.else.entirely();"

    # Act
    result = ma.is_temporal_chain_call(line, None, frozenset())

    # Assert
    assert result is False


def test_is_temporal_chain_call_owner_in_receivers_short_circuits() -> None:
    assert ma.is_temporal_chain_call("anything", "t", frozenset({"t"})) is True


# --------------------------------------------------------------------------- #
# Web API helpers
# --------------------------------------------------------------------------- #


def test_is_web_api_receiver_returns_false_when_owner_none() -> None:
    assert ma.is_web_api_receiver(None, frozenset({"params"})) is False


def test_is_web_api_receiver_matches_when_owner_in_set() -> None:
    assert ma.is_web_api_receiver("params", frozenset({"params"})) is True


def test_collect_web_api_receivers_returns_empty_for_empty_text() -> None:
    assert ma.collect_web_api_receivers("") == frozenset()


# --------------------------------------------------------------------------- #
# is_es2024_static_factory
# --------------------------------------------------------------------------- #


def test_is_es2024_static_factory_returns_false_for_empty() -> None:
    assert ma.is_es2024_static_factory("") is False


def test_is_es2024_static_factory_recognizes_promise_with_resolvers() -> None:
    line = "const { promise, resolve } = Promise.withResolvers();"
    assert ma.is_es2024_static_factory(line) is True


def test_is_es2024_static_factory_recognizes_array_from_async() -> None:
    line = "const result = await Array.fromAsync(iterable);"
    assert ma.is_es2024_static_factory(line) is True


def test_is_es2024_static_factory_returns_false_for_unknown() -> None:
    line = "const x = somethingElse();"
    assert ma.is_es2024_static_factory(line) is False


# --------------------------------------------------------------------------- #
# skip_extension / skip_path / is_hot_path
# --------------------------------------------------------------------------- #


def test_skip_extension_returns_true_for_empty_path() -> None:
    assert ma.skip_extension("") is True


def test_skip_extension_returns_true_for_python_file() -> None:
    assert ma.skip_extension("src/foo.py") is True


def test_skip_extension_returns_false_for_regular_ts() -> None:
    assert ma.skip_extension("src/foo.ts") is False


def test_skip_path_returns_true_for_empty_path() -> None:
    assert ma.skip_path("") is True


def test_skip_path_returns_false_for_src_path() -> None:
    assert ma.skip_path("src/foo.ts") is False


def test_is_hot_path_returns_true_for_crypto_dir() -> None:
    assert ma.is_hot_path("src/crypto/cipher.ts") is True


def test_is_hot_path_returns_false_for_regular_path() -> None:
    assert ma.is_hot_path("src/components/Button.tsx") is False


# --------------------------------------------------------------------------- #
# hit_uses_receiver edge cases
# --------------------------------------------------------------------------- #


def test_hit_uses_receiver_returns_false_for_empty_line() -> None:
    assert ma.hit_uses_receiver("", frozenset({"x"})) is False


def test_hit_uses_receiver_returns_false_for_empty_receivers() -> None:
    assert ma.hit_uses_receiver("x.push(y)", frozenset()) is False


def test_hit_uses_receiver_skips_empty_name_in_set() -> None:
    # Arrange: receivers contains an empty string mixed with a real name.
    receivers = frozenset({"", "state"})
    line = "state.value += 1"

    # Act
    result = ma.hit_uses_receiver(line, receivers)

    # Assert
    assert result is True


def test_hit_uses_receiver_matches_dot_access() -> None:
    line = "    state.items.push(value);"
    assert ma.hit_uses_receiver(line, frozenset({"state"})) is True


def test_hit_uses_receiver_matches_word_boundary() -> None:
    line = "total += 1;"
    assert ma.hit_uses_receiver(line, frozenset({"total"})) is True


# --------------------------------------------------------------------------- #
# is_in_state_mgmt_scope per-library branches
# --------------------------------------------------------------------------- #


def test_state_scope_jotai_atom() -> None:
    window = "import { atom, useAtom } from 'jotai';\nconst countAtom = atom(0);\nconst [count, setCount] = useAtom(countAtom);"
    matched, label = ma.is_in_state_mgmt_scope(window, "src/store.ts")
    assert matched is True
    assert label == "jotai-atom"


def test_state_scope_recoil_atom() -> None:
    window = "import { atom, useRecoilState } from 'recoil';\nconst counterState = atom({ key: 'counter', default: 0 });\nuseRecoilState(counterState);"
    matched, label = ma.is_in_state_mgmt_scope(window, "src/recoil.ts")
    assert matched is True
    assert label == "recoil-atom"


def test_state_scope_xstate_assign() -> None:
    window = "import { createMachine, assign } from 'xstate';\nconst inc = assign({ count: ctx => ctx.count + 1 });"
    matched, label = ma.is_in_state_mgmt_scope(window, "src/machine.ts")
    assert matched is True
    assert label == "xstate-assign"


def test_state_scope_solid_store() -> None:
    window = "import { createStore } from 'solid-js/store';\nconst [state, setState] = createStore({ count: 0 });"
    matched, label = ma.is_in_state_mgmt_scope(window, "src/store.ts")
    assert matched is True
    assert label == "solid-store"


def test_state_scope_nanostores() -> None:
    window = (
        "import { atom } from 'nanostores';\nconst $count = atom(0);\n$count.set(1);"
    )
    matched, label = ma.is_in_state_mgmt_scope(window, "src/store.ts")
    assert matched is True
    assert label == "nanostores"


def test_state_scope_legendapp_state() -> None:
    window = "import { observable } from '@legendapp/state';\nconst state$ = observable({ count: 0 });\nstate$.count.set(1);"
    matched, label = ma.is_in_state_mgmt_scope(window, "src/legend.ts")
    assert matched is True
    assert label == "legendapp-state"


def test_state_scope_tanstack_store() -> None:
    window = "import { Store } from '@tanstack/store';\nconst store = new Store({ count: 0 });\nstore.setState((s) => ({ count: s.count + 1 }));"
    matched, label = ma.is_in_state_mgmt_scope(window, "src/tanstack.ts")
    assert matched is True
    assert label == "tanstack-store"


def test_state_scope_vue_readonly() -> None:
    window = "import { ref, reactive } from 'vue';\nconst state = reactive({ count: 0 });\nstate.count = 1;"
    matched, label = ma.is_in_state_mgmt_scope(window, "src/vue-state.ts")
    assert matched is True
    assert label == "vue-readonly"


def test_state_scope_svelte_runes() -> None:
    window = "let count = $state(0);\ncount += 1;"
    matched, label = ma.is_in_state_mgmt_scope(window, "src/Component.svelte")
    assert matched is True
    assert label == "svelte-runes"


def test_state_scope_returns_false_for_empty_window() -> None:
    matched, label = ma.is_in_state_mgmt_scope("", "src/x.ts")
    assert matched is False
    assert label is None


def test_state_scope_falls_back_to_filename_pattern() -> None:
    # Arrange: window has no library imports, but filename matches state-mgmt pattern
    window = "function makeReducer() { return (state) => state; }"
    matched, label = ma.is_in_state_mgmt_scope(window, "src/userSlice.ts")

    # Assert
    assert matched is True
    assert label == "state-mgmt-filename"
