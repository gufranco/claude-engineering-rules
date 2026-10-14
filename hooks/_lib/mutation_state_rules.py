from __future__ import annotations

import re
from collections.abc import Callable

from .mutation_state_patterns import (
    ANGULAR_SIGNAL_VAR_DECL_PATTERN,
    ANGULAR_SIGNALS_IMPORT_PATTERN,
    ANGULAR_SIGNALS_USAGE_PATTERN,
    EFFECT_DATA_IMPORT_PATTERN,
    EFFECT_DATA_USAGE_PATTERN,
    EFFECT_TS_GEN_PATTERN,
    EFFECT_TS_IMPORT_PATTERN,
    EFFECT_TS_REF_PATTERN,
    HMR_BOUNDARY_PATTERN,
    IMMER_PRODUCE_PATTERN,
    JOTAI_IMPORT_PATTERN,
    JOTAI_USAGE_PATTERN,
    LEGENDAPP_IMPORT_PATTERN,
    LEGENDAPP_USAGE_PATTERN,
    LEGENDAPP_VAR_DECL_PATTERN,
    MOBX_ACTION_PATTERN,
    MUTATIVE_CREATE_PATTERN,
    NANOSTORES_IMPORT_PATTERN,
    NANOSTORES_USAGE_PATTERN,
    NANOSTORES_VAR_DECL_PATTERN,
    PINIA_STORE_PATTERN,
    PREACT_SIGNAL_VAR_DECL_PATTERN,
    PREACT_SIGNALS_IMPORT_PATTERN,
    PREACT_SIGNALS_USAGE_PATTERN,
    QWIK_SIGNAL_VAR_DECL_PATTERN,
    QWIK_SIGNALS_IMPORT_PATTERN,
    QWIK_SIGNALS_USAGE_PATTERN,
    REACT_19_FORMSTATE_PATTERN,
    REACT_SERVER_DIRECTIVE_PATTERN,
    REACT_USE_REDUCER_PATTERN,
    RECOIL_IMPORT_PATTERN,
    RECOIL_USAGE_PATTERN,
    REDUX_TOOLKIT_PATTERN,
    SHADOW_REALM_IMPORT_PATTERN,
    SHADOW_REALM_USAGE_PATTERN,
    SOLID_DIRECT_VAR_DECL_PATTERN,
    SOLID_PRODUCE_ONLY_PATTERN,
    SOLID_PRODUCE_PATTERN,
    SOLID_RECONCILE_PATTERN,
    SOLID_STORE_IMPORT_PATTERN,
    SOLID_STORE_USAGE_PATTERN,
    SOLID_TUPLE_VAR_DECL_PATTERN,
    SVELTE_RUNES_PATTERN,
    SVELTE_RUNES_VAR_DECL_PATTERN,
    SYMBOL_METADATA_USAGE_PATTERN,
    TANSTACK_STORE_IMPORT_PATTERN,
    TANSTACK_STORE_USAGE_PATTERN,
    TC39_SIGNAL_VAR_DECL_PATTERN,
    TC39_SIGNALS_IMPORT_PATTERN,
    TC39_SIGNALS_USAGE_PATTERN,
    VALTIO_IMPORT_PATTERN,
    VALTIO_PROXY_PATTERN,
    VALTIO_VAR_DECL_PATTERN,
    VUE_READONLY_IMPORT_PATTERN,
    VUE_READONLY_USAGE_PATTERN,
    VUE_REACTIVE_VAR_DECL_PATTERN,
    VUEX_MUTATIONS_PATTERN,
    XSTATE_ASSIGN_PATTERN,
    XSTATE_IMPORT_PATTERN,
    YJS_TYPE_PATTERN,
    ZUSTAND_PRODUCE_PATTERN,
)

ScopePredicate = Callable[[str, str], bool]
ScopeRule = tuple[str, ScopePredicate]
ReceiverRule = tuple[str, ScopePredicate, tuple[re.Pattern[str], ...]]

SVELTE_FILE_SUFFIXES = (".svelte", ".svelte.ts", ".svelte.js")


def _any_of(*patterns: re.Pattern[str]) -> ScopePredicate:
    def matches(window: str, _file_path: str) -> bool:
        return any(pattern.search(window) for pattern in patterns)

    return matches


def _all_of(*patterns: re.Pattern[str]) -> ScopePredicate:
    def matches(window: str, _file_path: str) -> bool:
        return all(pattern.search(window) for pattern in patterns)

    return matches


def _solid_reconcile(window: str, _file_path: str) -> bool:
    return bool(
        SOLID_STORE_IMPORT_PATTERN.search(window)
        and SOLID_PRODUCE_PATTERN.search(window)
        and SOLID_RECONCILE_PATTERN.search(window)
        and not SOLID_PRODUCE_ONLY_PATTERN.search(window)
    )


def _svelte_runes(window: str, file_path: str) -> bool:
    return bool(SVELTE_RUNES_PATTERN.search(window)) and file_path.lower().endswith(
        SVELTE_FILE_SUFFIXES
    )


def _effect_ts(window: str, _file_path: str) -> bool:
    return bool(
        EFFECT_TS_IMPORT_PATTERN.search(window)
        and (
            EFFECT_TS_GEN_PATTERN.search(window) or EFFECT_TS_REF_PATTERN.search(window)
        )
    )


def _svelte_file(_full_text: str, file_path: str) -> bool:
    return bool(file_path) and file_path.lower().endswith(SVELTE_FILE_SUFFIXES)


SCOPE_RULES: tuple[ScopeRule, ...] = (
    ("zustand-produce", _any_of(ZUSTAND_PRODUCE_PATTERN)),
    ("immer-produce", _any_of(IMMER_PRODUCE_PATTERN)),
    ("mutative-create", _any_of(MUTATIVE_CREATE_PATTERN)),
    ("redux-toolkit", _any_of(REDUX_TOOLKIT_PATTERN)),
    ("pinia-define-store", _any_of(PINIA_STORE_PATTERN)),
    ("vuex-mutations", _any_of(VUEX_MUTATIONS_PATTERN)),
    ("mobx-action", _any_of(MOBX_ACTION_PATTERN)),
    ("yjs-crdt", _any_of(YJS_TYPE_PATTERN)),
    ("valtio-proxy", _all_of(VALTIO_IMPORT_PATTERN, VALTIO_PROXY_PATTERN)),
    ("jotai-atom", _all_of(JOTAI_IMPORT_PATTERN, JOTAI_USAGE_PATTERN)),
    ("recoil-atom", _all_of(RECOIL_IMPORT_PATTERN, RECOIL_USAGE_PATTERN)),
    ("xstate-assign", _all_of(XSTATE_IMPORT_PATTERN, XSTATE_ASSIGN_PATTERN)),
    ("solid-reconcile", _solid_reconcile),
    ("solid-produce", _all_of(SOLID_STORE_IMPORT_PATTERN, SOLID_PRODUCE_PATTERN)),
    ("solid-store", _all_of(SOLID_STORE_IMPORT_PATTERN, SOLID_STORE_USAGE_PATTERN)),
    ("nanostores", _all_of(NANOSTORES_IMPORT_PATTERN, NANOSTORES_USAGE_PATTERN)),
    ("legendapp-state", _all_of(LEGENDAPP_IMPORT_PATTERN, LEGENDAPP_USAGE_PATTERN)),
    (
        "tanstack-store",
        _all_of(TANSTACK_STORE_IMPORT_PATTERN, TANSTACK_STORE_USAGE_PATTERN),
    ),
    ("effect-data", _all_of(EFFECT_DATA_IMPORT_PATTERN, EFFECT_DATA_USAGE_PATTERN)),
    ("vue-readonly", _all_of(VUE_READONLY_IMPORT_PATTERN, VUE_READONLY_USAGE_PATTERN)),
    ("svelte-runes", _svelte_runes),
    (
        "angular-signals",
        _all_of(ANGULAR_SIGNALS_IMPORT_PATTERN, ANGULAR_SIGNALS_USAGE_PATTERN),
    ),
    ("qwik-signals", _all_of(QWIK_SIGNALS_IMPORT_PATTERN, QWIK_SIGNALS_USAGE_PATTERN)),
    (
        "preact-signals",
        _all_of(PREACT_SIGNALS_IMPORT_PATTERN, PREACT_SIGNALS_USAGE_PATTERN),
    ),
    ("tc39-signals", _all_of(TC39_SIGNALS_IMPORT_PATTERN, TC39_SIGNALS_USAGE_PATTERN)),
    ("effect-ts", _effect_ts),
    (
        "react-19-state-hooks",
        _any_of(REACT_19_FORMSTATE_PATTERN, REACT_USE_REDUCER_PATTERN),
    ),
    ("react-server-action", _any_of(REACT_SERVER_DIRECTIVE_PATTERN)),
    ("shadow-realm", _any_of(SHADOW_REALM_IMPORT_PATTERN, SHADOW_REALM_USAGE_PATTERN)),
    ("symbol-metadata", _any_of(SYMBOL_METADATA_USAGE_PATTERN)),
    ("hmr-boundary", _any_of(HMR_BOUNDARY_PATTERN)),
)

RECEIVER_RULES: tuple[ReceiverRule, ...] = (
    ("valtio-proxy", _any_of(VALTIO_IMPORT_PATTERN), (VALTIO_VAR_DECL_PATTERN,)),
    (
        "solid-store",
        _any_of(SOLID_STORE_IMPORT_PATTERN),
        (SOLID_DIRECT_VAR_DECL_PATTERN, SOLID_TUPLE_VAR_DECL_PATTERN),
    ),
    (
        "legendapp-state",
        _any_of(LEGENDAPP_IMPORT_PATTERN),
        (LEGENDAPP_VAR_DECL_PATTERN,),
    ),
    (
        "vue-reactive",
        _any_of(VUE_READONLY_IMPORT_PATTERN),
        (VUE_REACTIVE_VAR_DECL_PATTERN,),
    ),
    ("nanostores", _any_of(NANOSTORES_IMPORT_PATTERN), (NANOSTORES_VAR_DECL_PATTERN,)),
    ("svelte-runes", _svelte_file, (SVELTE_RUNES_VAR_DECL_PATTERN,)),
    (
        "angular-signals",
        _any_of(ANGULAR_SIGNALS_IMPORT_PATTERN),
        (ANGULAR_SIGNAL_VAR_DECL_PATTERN,),
    ),
    (
        "qwik-signals",
        _any_of(QWIK_SIGNALS_IMPORT_PATTERN),
        (QWIK_SIGNAL_VAR_DECL_PATTERN,),
    ),
    (
        "preact-signals",
        _any_of(PREACT_SIGNALS_IMPORT_PATTERN),
        (PREACT_SIGNAL_VAR_DECL_PATTERN,),
    ),
    (
        "tc39-signals",
        _any_of(TC39_SIGNALS_IMPORT_PATTERN),
        (TC39_SIGNAL_VAR_DECL_PATTERN,),
    ),
)
