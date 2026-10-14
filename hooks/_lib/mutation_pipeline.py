from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from .mutation_allowlists import is_hot_path
from .mutation_confidence import TYPED_SUFFIX_HINTS, score_finding
from .mutation_detectors_assignments import (
    detect_compound_assignment,
    detect_computed_or_index_assignment,
    detect_increment_decrement,
    detect_optional_chain_assignment,
    detect_private_field_assignment,
    detect_property_assignment,
    detect_symbol_key_assignment,
)
from .mutation_detectors_binary import (
    detect_arraybuffer_transfer,
    detect_atomics_mutations,
    detect_dataview_setters,
    detect_typed_array_mutations,
    detect_uint8_base64_setter,
    detect_uint8array_set_buffer_offset,
    detect_wasm_memory_grow,
)
from .mutation_detectors_bindings import (
    detect_let_could_be_const,
    detect_param_reassignment,
    detect_static_block_mutation,
    filter_matches_in_canonical_static_blocks,
)
from .mutation_detectors_builtins import (
    detect_async_iterator_return_throw,
    detect_delete_operator,
    detect_global_assignment,
    detect_object_assign_target_mutation,
    detect_object_define_setprototype,
    detect_reflect_mutations,
)
from .mutation_detectors_core import Match
from .mutation_detectors_methods import (
    detect_array_pop_shift_unshift_splice_reverse_fill_copywithin,
    detect_array_push,
    detect_array_sort,
    detect_bracket_dispatch,
    detect_map_set_collection_mutations,
    detect_map_upsert,
)
from .mutation_detectors_runtime import (
    detect_date_setters,
    detect_finalization_registry,
    detect_for_await_push_pattern,
    detect_object_groupby_push,
    detect_proxy_mutating_traps,
    detect_weakref_then_mutate,
)
from .mutation_detectors_stores import (
    detect_effect_ts_ref_value_assign,
    detect_nanostores_computed_write,
    detect_recoil_deprecation_pointer,
    detect_svelte_derived_reassign,
    detect_tanstack_store_state_write,
    detect_vue_shallow_readonly_nested_write,
)
from .mutation_detectors_transactions import (
    detect_automerge_direct_mutation,
    detect_mobx_observable_outside_action,
    detect_xstate_non_assign_context_write,
    detect_yjs_mutation_outside_transact,
)
from .mutation_detectors_webapi import (
    detect_form_data_mutations,
    detect_headers_mutations,
    detect_url_search_params_mutations,
)
from .mutation_source_map import is_transpiled_path, load_source_map, map_to_original

DetectorFn = Callable[[str, str | None, str], list[Match]]

TYPED_ARRAY_OVERLAP_DETECTORS: frozenset[str] = frozenset(
    {"array.fill", "array.sort", "array.reverse", "array.copyWithin"}
)


class Gate(Enum):
    ALWAYS = "always"
    COLD_ONLY = "cold-only"
    HOT_TRIMMED = "hot-trimmed"
    FULL_FILE = "full-file"
    OPTIONAL_CHAIN = "optional-chain"


@dataclass(frozen=True)
class ScanRequest:
    text: str
    lang: str | None
    file_path: str
    is_full_file: bool
    optional_chain: bool


@dataclass(frozen=True)
class _ScanContext:
    request: ScanRequest
    hot: bool


DETECTORS: tuple[tuple[DetectorFn, Gate], ...] = (
    (detect_array_push, Gate.ALWAYS),
    (detect_array_sort, Gate.HOT_TRIMMED),
    (detect_array_pop_shift_unshift_splice_reverse_fill_copywithin, Gate.HOT_TRIMMED),
    (detect_bracket_dispatch, Gate.ALWAYS),
    (detect_map_set_collection_mutations, Gate.ALWAYS),
    (detect_typed_array_mutations, Gate.COLD_ONLY),
    (detect_date_setters, Gate.ALWAYS),
    (detect_url_search_params_mutations, Gate.ALWAYS),
    (detect_headers_mutations, Gate.ALWAYS),
    (detect_form_data_mutations, Gate.ALWAYS),
    (detect_dataview_setters, Gate.COLD_ONLY),
    (detect_uint8array_set_buffer_offset, Gate.COLD_ONLY),
    (detect_atomics_mutations, Gate.ALWAYS),
    (detect_wasm_memory_grow, Gate.ALWAYS),
    (detect_proxy_mutating_traps, Gate.ALWAYS),
    (detect_weakref_then_mutate, Gate.ALWAYS),
    (detect_finalization_registry, Gate.ALWAYS),
    (detect_for_await_push_pattern, Gate.ALWAYS),
    (detect_uint8_base64_setter, Gate.COLD_ONLY),
    (detect_map_upsert, Gate.ALWAYS),
    (detect_arraybuffer_transfer, Gate.ALWAYS),
    (detect_object_groupby_push, Gate.ALWAYS),
    (detect_property_assignment, Gate.ALWAYS),
    (detect_computed_or_index_assignment, Gate.ALWAYS),
    (detect_compound_assignment, Gate.ALWAYS),
    (detect_increment_decrement, Gate.ALWAYS),
    (detect_object_assign_target_mutation, Gate.ALWAYS),
    (detect_object_define_setprototype, Gate.ALWAYS),
    (detect_reflect_mutations, Gate.ALWAYS),
    (detect_delete_operator, Gate.ALWAYS),
    (detect_global_assignment, Gate.ALWAYS),
    (detect_param_reassignment, Gate.ALWAYS),
    (detect_private_field_assignment, Gate.ALWAYS),
    (detect_symbol_key_assignment, Gate.ALWAYS),
    (detect_static_block_mutation, Gate.ALWAYS),
    (detect_async_iterator_return_throw, Gate.ALWAYS),
    (detect_automerge_direct_mutation, Gate.ALWAYS),
    (detect_effect_ts_ref_value_assign, Gate.ALWAYS),
    (detect_mobx_observable_outside_action, Gate.ALWAYS),
    (detect_nanostores_computed_write, Gate.ALWAYS),
    (detect_recoil_deprecation_pointer, Gate.ALWAYS),
    (detect_svelte_derived_reassign, Gate.ALWAYS),
    (detect_tanstack_store_state_write, Gate.ALWAYS),
    (detect_vue_shallow_readonly_nested_write, Gate.ALWAYS),
    (detect_xstate_non_assign_context_write, Gate.ALWAYS),
    (detect_yjs_mutation_outside_transact, Gate.ALWAYS),
    (detect_let_could_be_const, Gate.FULL_FILE),
    (detect_optional_chain_assignment, Gate.OPTIONAL_CHAIN),
)


def _gate_is_open(gate: Gate, context: _ScanContext) -> bool:
    if gate is Gate.COLD_ONLY:
        return not context.hot
    if gate is Gate.FULL_FILE:
        return context.request.is_full_file
    if gate is Gate.OPTIONAL_CHAIN:
        return context.request.optional_chain
    return True


def _run_detector(
    detector: DetectorFn, gate: Gate, context: _ScanContext
) -> list[Match]:
    if not _gate_is_open(gate, context):
        return []
    request = context.request
    found = detector(request.text, request.lang, request.file_path)
    if gate is Gate.HOT_TRIMMED and context.hot:
        return [m for m in found if m.detector not in TYPED_ARRAY_OVERLAP_DETECTORS]
    return found


def detect_all(request: ScanRequest) -> list[Match]:
    context = _ScanContext(request=request, hot=is_hot_path(request.file_path))
    matches = [
        match
        for detector, gate in DETECTORS
        for match in _run_detector(detector, gate, context)
    ]
    return filter_matches_in_canonical_static_blocks(matches, request.text)


def _receiver_known(match: Match) -> bool:
    receiver = match.metadata.get("receiver", "") if match.metadata else ""
    if not receiver:
        return False
    head = receiver.split(".", 1)[0].split("[", 1)[0].strip()
    return any(head.endswith(suffix) for suffix in TYPED_SUFFIX_HINTS)


def enrich_with_confidence(matches: list[Match], file_path: str) -> list[Match]:
    return [
        dataclasses.replace(
            m,
            metadata={
                **(m.metadata or {}),
                "confidence": str(
                    score_finding(
                        m.detector,
                        ast_confirmed=bool(m.node_type),
                        receiver_known=_receiver_known(m),
                        file_path=file_path,
                    )
                ),
            },
        )
        for m in matches
    ]


def _remap_match(match: Match, file_path: str, mapped: tuple[str, int, int]) -> Match:
    source_path, orig_line, orig_col = mapped
    metadata = {
        **(match.metadata or {}),
        "generated_file": file_path,
        "generated_line": str(match.line),
        "generated_col": str(match.col),
        "source_file": source_path,
    }
    return dataclasses.replace(match, line=orig_line, col=orig_col, metadata=metadata)


def remap_via_source_map(
    file_path: str, matches: list[Match]
) -> tuple[str, list[Match]]:
    source_map = load_source_map(file_path) if is_transpiled_path(file_path) else None
    if source_map is None:
        return file_path, matches
    mapped = [(m, map_to_original(source_map, m.line, m.col)) for m in matches]
    remapped = [
        m if target is None else _remap_match(m, file_path, target)
        for m, target in mapped
    ]
    sources = [target[0] for _m, target in mapped if target is not None]
    return (sources[0] if sources else "") or file_path, remapped
