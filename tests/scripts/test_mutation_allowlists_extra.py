from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import mutation_allowlists as ma  # noqa: E402


def test_is_dom_receiver_returns_false_for_none() -> None:
    # Arrange
    receiver = None

    # Act
    result = ma.is_dom_receiver(receiver)

    # Assert
    assert result is False


def test_is_dom_receiver_returns_false_for_empty_string() -> None:
    # Arrange
    receiver = ""

    # Act
    result = ma.is_dom_receiver(receiver)

    # Assert
    assert result is False


def test_is_dom_receiver_returns_false_for_whitespace_only() -> None:
    # Arrange
    receiver = "   "

    # Act
    result = ma.is_dom_receiver(receiver)

    # Assert
    assert result is False


def test_is_dom_assignment_returns_false_when_no_signals() -> None:
    # Arrange
    receiver = "notADomReceiver"

    # Act
    result = ma.is_dom_assignment(receiver, "someRandomProp")

    # Assert
    assert result is False


def test_collect_temporal_receivers_returns_empty_for_empty_text() -> None:
    # Arrange
    text = ""

    # Act
    result = ma.collect_temporal_receivers(text)

    # Assert
    assert result == frozenset()


def test_is_temporal_chain_call_returns_false_for_empty_line() -> None:
    # Arrange
    line = ""

    # Act
    result = ma.is_temporal_chain_call(line, None, frozenset())

    # Assert
    assert result is False


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
    # Arrange
    line = "anything"

    # Act
    result = ma.is_temporal_chain_call(line, "t", frozenset({"t"}))

    # Assert
    assert result is True


def test_is_web_api_receiver_returns_false_when_owner_none() -> None:
    # Arrange
    receivers = frozenset({"params"})

    # Act
    result = ma.is_web_api_receiver(None, receivers)

    # Assert
    assert result is False


def test_is_web_api_receiver_matches_when_owner_in_set() -> None:
    # Arrange
    owner = "params"

    # Act
    result = ma.is_web_api_receiver(owner, frozenset({"params"}))

    # Assert
    assert result is True


def test_collect_web_api_receivers_returns_empty_for_empty_text() -> None:
    # Arrange
    text = ""

    # Act
    result = ma.collect_web_api_receivers(text)

    # Assert
    assert result == frozenset()


def test_is_es2024_static_factory_returns_false_for_empty() -> None:
    # Arrange
    line = ""

    # Act
    result = ma.is_es2024_static_factory(line)

    # Assert
    assert result is False


def test_is_es2024_static_factory_recognizes_promise_with_resolvers() -> None:
    # Arrange
    line = "const { promise, resolve } = Promise.withResolvers();"

    # Act
    result = ma.is_es2024_static_factory(line)

    # Assert
    assert result is True


def test_is_es2024_static_factory_recognizes_array_from_async() -> None:
    # Arrange
    line = "const result = await Array.fromAsync(iterable);"

    # Act
    result = ma.is_es2024_static_factory(line)

    # Assert
    assert result is True


def test_is_es2024_static_factory_returns_false_for_unknown() -> None:
    # Arrange
    line = "const x = somethingElse();"

    # Act
    result = ma.is_es2024_static_factory(line)

    # Assert
    assert result is False


def test_skip_extension_returns_true_for_empty_path() -> None:
    # Arrange
    file_path = ""

    # Act
    result = ma.skip_extension(file_path)

    # Assert
    assert result is True


def test_skip_extension_returns_true_for_python_file() -> None:
    # Arrange
    file_path = "src/foo.py"

    # Act
    result = ma.skip_extension(file_path)

    # Assert
    assert result is True


def test_skip_extension_returns_false_for_regular_ts() -> None:
    # Arrange
    file_path = "src/foo.ts"

    # Act
    result = ma.skip_extension(file_path)

    # Assert
    assert result is False


def test_skip_path_returns_true_for_empty_path() -> None:
    # Arrange
    file_path = ""

    # Act
    result = ma.skip_path(file_path)

    # Assert
    assert result is True


def test_skip_path_returns_false_for_src_path() -> None:
    # Arrange
    file_path = "src/foo.ts"

    # Act
    result = ma.skip_path(file_path)

    # Assert
    assert result is False


def test_is_hot_path_returns_true_for_crypto_dir() -> None:
    # Arrange
    file_path = "src/crypto/cipher.ts"

    # Act
    result = ma.is_hot_path(file_path)

    # Assert
    assert result is True


def test_is_hot_path_returns_false_for_regular_path() -> None:
    # Arrange
    file_path = "src/components/Button.tsx"

    # Act
    result = ma.is_hot_path(file_path)

    # Assert
    assert result is False


def test_hit_uses_receiver_returns_false_for_empty_line() -> None:
    # Arrange
    hit_line = ""

    # Act
    result = ma.hit_uses_receiver(hit_line, frozenset({"x"}))

    # Assert
    assert result is False


def test_hit_uses_receiver_returns_false_for_empty_receivers() -> None:
    # Arrange
    hit_line = "x.push(y)"

    # Act
    result = ma.hit_uses_receiver(hit_line, frozenset())

    # Assert
    assert result is False


def test_hit_uses_receiver_skips_empty_name_in_set() -> None:
    # Arrange
    receivers = frozenset({"", "state"})
    line = "state.value += 1"

    # Act
    result = ma.hit_uses_receiver(line, receivers)

    # Assert
    assert result is True


def test_hit_uses_receiver_matches_dot_access() -> None:
    # Arrange
    line = "    state.items.push(value);"

    # Act
    result = ma.hit_uses_receiver(line, frozenset({"state"}))

    # Assert
    assert result is True


def test_hit_uses_receiver_matches_word_boundary() -> None:
    # Arrange
    line = "total += 1;"

    # Act
    result = ma.hit_uses_receiver(line, frozenset({"total"}))

    # Assert
    assert result is True


def test_state_scope_jotai_atom() -> None:
    # Arrange
    window = "import { atom, useAtom } from 'jotai';\nconst countAtom = atom(0);\nconst [count, setCount] = useAtom(countAtom);"

    # Act
    matched, label = ma.is_in_state_mgmt_scope(window, "src/store.ts")

    # Assert
    assert matched is True
    assert label == "jotai-atom"


def test_state_scope_recoil_atom() -> None:
    # Arrange
    window = "import { atom, useRecoilState } from 'recoil';\nconst counterState = atom({ key: 'counter', default: 0 });\nuseRecoilState(counterState);"

    # Act
    matched, label = ma.is_in_state_mgmt_scope(window, "src/recoil.ts")

    # Assert
    assert matched is True
    assert label == "recoil-atom"


def test_state_scope_xstate_assign() -> None:
    # Arrange
    window = "import { createMachine, assign } from 'xstate';\nconst inc = assign({ count: ctx => ctx.count + 1 });"

    # Act
    matched, label = ma.is_in_state_mgmt_scope(window, "src/machine.ts")

    # Assert
    assert matched is True
    assert label == "xstate-assign"


def test_state_scope_solid_store() -> None:
    # Arrange
    window = "import { createStore } from 'solid-js/store';\nconst [state, setState] = createStore({ count: 0 });"

    # Act
    matched, label = ma.is_in_state_mgmt_scope(window, "src/store.ts")

    # Assert
    assert matched is True
    assert label == "solid-store"


def test_state_scope_nanostores() -> None:
    # Arrange
    window = (
        "import { atom } from 'nanostores';\nconst $count = atom(0);\n$count.set(1);"
    )

    # Act
    matched, label = ma.is_in_state_mgmt_scope(window, "src/store.ts")

    # Assert
    assert matched is True
    assert label == "nanostores"


def test_state_scope_legendapp_state() -> None:
    # Arrange
    window = "import { observable } from '@legendapp/state';\nconst state$ = observable({ count: 0 });\nstate$.count.set(1);"

    # Act
    matched, label = ma.is_in_state_mgmt_scope(window, "src/legend.ts")

    # Assert
    assert matched is True
    assert label == "legendapp-state"


def test_state_scope_tanstack_store() -> None:
    # Arrange
    window = "import { Store } from '@tanstack/store';\nconst store = new Store({ count: 0 });\nstore.setState((s) => ({ count: s.count + 1 }));"

    # Act
    matched, label = ma.is_in_state_mgmt_scope(window, "src/tanstack.ts")

    # Assert
    assert matched is True
    assert label == "tanstack-store"


def test_state_scope_vue_readonly() -> None:
    # Arrange
    window = "import { ref, reactive } from 'vue';\nconst state = reactive({ count: 0 });\nstate.count = 1;"

    # Act
    matched, label = ma.is_in_state_mgmt_scope(window, "src/vue-state.ts")

    # Assert
    assert matched is True
    assert label == "vue-readonly"


def test_state_scope_svelte_runes() -> None:
    # Arrange
    window = "let count = $state(0);\ncount += 1;"

    # Act
    matched, label = ma.is_in_state_mgmt_scope(window, "src/Component.svelte")

    # Assert
    assert matched is True
    assert label == "svelte-runes"


def test_state_scope_returns_false_for_empty_window() -> None:
    # Arrange
    window = ""

    # Act
    matched, label = ma.is_in_state_mgmt_scope(window, "src/x.ts")

    # Assert
    assert matched is False
    assert label is None


def test_state_scope_falls_back_to_filename_pattern() -> None:
    # Arrange
    window = "function makeReducer() { return (state) => state; }"

    # Act
    matched, label = ma.is_in_state_mgmt_scope(window, "src/userSlice.ts")

    # Assert
    assert matched is True
    assert label == "state-mgmt-filename"
