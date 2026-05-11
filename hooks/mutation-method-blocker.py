#!/usr/bin/env python3
"""mutation-method-blocker v2.0

PreToolUse hook that blocks in-place mutation of arrays, objects, collections,
TypedArrays, Dates, and parameters in JavaScript and TypeScript code.

Rule source: ~/.claude/rules/code-style.md "Immutability".

Detector categories (50+ patterns):

  - Array prototype: push, pop, shift, unshift, splice, sort, reverse, fill,
    copyWithin, plus bracket-string dispatch (`arr['push'](x)`).
  - Map / Set / WeakMap / WeakSet prototype: set, delete, clear, add.
  - TypedArray prototype: set, fill, sort, reverse, copyWithin (auto-allowed
    in hot-path directories: crypto, codec, image, audio, parser, wasm, ...).
  - Property assignment: `obj.prop = v`, `obj['prop'] = v`, `arr[i] = v`.
  - Compound assignment: `obj.prop += v` plus 14 other operators.
  - Increment / decrement: `obj.prop++`, `--obj.prop`.
  - Object utility: Object.assign with non-fresh target, defineProperty,
    defineProperties, setPrototypeOf, plus the four Reflect counterparts.
  - delete operator on member access.
  - Global mutation: globalThis, window, self, process.env writes.
  - Date prototype setters: 16 methods covering local and UTC variants.
  - Parameter reassignment, with `no-param-reassign` allowlist defaults.
  - `let`-could-be-`const` (full-file Write payloads only).

Auto-allowed scopes (no flag):

  - Framework navigation: router.push, history.push, navigation.push, ...
  - Stream / queue / response APIs: stream.push, ws.push, res.push, ...
  - Immer `produce`, Mutative `create`, Redux Toolkit slice and extraReducers,
    Pinia stores, Vuex mutations, MobX actions, Zustand `set(produce(...))`,
    Yjs CRDT types.
  - State-management filenames (`*Slice.ts`, `*Store.ts`, `*reducer.ts`).
  - TypedArray hot paths.

Suppression markers (per line):

  - `// claude-allow-mutation -- justification` honored when justified.
  - `// @claude-allow-mutation -- justification` at the top of the file
    suppresses every detector for that file.
  - Standard ESLint and TypeScript markers honored:
    `eslint-disable`, `eslint-disable-line`, `eslint-disable-next-line`,
    `@ts-expect-error`, `@ts-ignore`, `@ts-nocheck`,
    block ranges `/* eslint-disable */ ... /* eslint-enable */`.

Skipped paths:

  - Test files (.test.*, .spec.*, **/__tests__/**)
  - Build / tooling (**/scripts/**, **/bin/**, **/tools/**, **/cli/**)
  - This hook directory (~/.claude/hooks/**)
  - Migrations, seeds, e2e, fixtures, .d.ts, .config.* files.

Bypass envs:

  - MUTATION_METHOD_DISABLE=1            - full opt-out, audit-logged.
  - MUTATION_METHOD_AST=0                - regex-only mode (skip ast-grep escalation).
  - MUTATION_METHOD_FIX_SUGGESTIONS=0    - emit raw detector tags only, skip
                                           the `mutation_fix_suggestions.json`
                                           lookup. Useful for benchmarking and
                                           for downstream agents that prefer
                                           machine-readable output without
                                           prose hints.
  - MUTATION_METHOD_TS_PROJECT_SERVICE=1 - opt in to TS Project Service for
                                           type-aware readonly / URLSearchParams /
                                           TypedArray detection (requires Node +
                                           typescript >= 5.6 on PATH).
  - MUTATION_METHOD_DEBUG=1              - log helper subprocess and source-map
                                           failures to stderr.

Fix-suggestion lookup (item 171-174 of plan):

  Detector codes resolve to ES2023/ES2024+ replacement hints via
  `~/.claude/hooks/mutation_fix_suggestions.json`. Each detector tag maps
  to a stable `MMB001`...`MMB050+` code so consumers can correlate hits
  across hook versions. Dynamic codes (`date.setMonth`, `typed-array.fill`)
  fall back to category-prefix matches (`date.setter`, `typed-array`).
  Set `MUTATION_METHOD_FIX_SUGGESTIONS=0` to suppress all suggestions.

DOM and Web API stance (item 197-208 of plan):

  Mutations on DOM nodes, the `document` object, the `window` object, and
  CSS-related accessors (`.style`, `.classList`, `.dataset`) are OUT OF
  SCOPE. The DOM API is inherently mutating; flagging it would generate
  noise on every `element.innerHTML = '...'` line. Use a dedicated linter
  (`eslint-plugin-jsx-a11y`, `eslint-plugin-react`) for DOM hygiene.

  IndexedDB cursor / transaction mutations and Web Storage `setItem` /
  `removeItem` are also out of scope. The mutation hook governs JS values;
  the no-side-effect-at-module-level rule governs side-effect APIs.

  In scope (still flagged): `URLSearchParams`, `Headers`, `FormData`
  mutations because they mutate plain JS values that have non-mutating
  alternatives (`new URLSearchParams([...params, [k, v]])`).

Migration note:
v2 (2026-05-09) expanded coverage from 2 to 50+ patterns. Bypass env
unchanged; new opt-out: `MUTATION_METHOD_AST=0`.
v2.1 (2026-05-10) added the fix-suggestion lookup table and
`MUTATION_METHOD_FIX_SUGGESTIONS=0` opt-out.
v2.2 (2026-05-10) DOM-aware property assignment skips: `document.X = `,
`window.X = `, `element.style.color = `, `node.textContent = `, and the
40+ DOM accessor suffixes are silently allowed. URLSearchParams,
Headers, and FormData mutations remain in scope.

v2.3 (2026-05-10) TypedArray expansion: all 12 subtypes recognized
(`Int8Array`, `Uint8Array`, `Uint8ClampedArray`, `Int16Array`,
`Uint16Array`, `Int32Array`, `Uint32Array`, `Float16Array`,
`Float32Array`, `Float64Array`, `BigInt64Array`, `BigUint64Array`).
Five new hot-path directories: `dsp`, `signal`, `fft`, `ml`, `tensor`.

TypedArray confidence policy (per D40):

  - Hot-path directories: detector fully short-circuited, no flag.
    This is equivalent to "warning suppressed" because the DSP, ML,
    crypto, and codec domains rely on in-place writes by design.
  - Non-hot-path directories: clean block at confidence 5. Business
    logic that mutates a TypedArray almost certainly has a bug:
    either the buffer was created without `Object.freeze`-equivalent
    intent, or a non-mutating clone (`new Uint8Array(buffer)`) is
    feasible.

Project-local config (plan items 284-287):

  Place `<project-root>/.claude/mutation-allowlist.yml` (or `.yaml`,
  `.json`) to extend the built-in allowlists for one project. The
  hook walks parents of the file under analysis until a `.git`
  directory, a `package.json`, or a `pnpm-workspace.yaml` is found
  and uses that as the project root. The schema is pinned to
  version 1; unknown fields produce a stderr warning, never an
  error. Invalid configs fall back to built-in defaults silently.

  Example:

      # .claude/mutation-allowlist.yml
      version: 1
      framework_receivers:
        - customRouter
        - eventBus
      hot_path_segments:
        - /matrices/
      param_reassign_allowed_names:
        - draft
      disable_detectors:
        - array.push        # discouraged: prefer per-line suppression
      experimental_detectors:
        - OPTIONAL_CHAIN_ASSIGN

  The full schema lives at
  `~/.claude/schemas/mutation-allowlist.schema.json` (Draft 7,
  validated via `jsonschema` when available).

Experimental detectors (plan items 291-293):

  Detectors gated by `MUTATION_METHOD_EXPERIMENTAL_<NAME>=1` are off
  by default and ship behind individual flags so new detection can
  roll out without breaking existing users.

  Active flags:

    - MUTATION_METHOD_EXPERIMENTAL_OPTIONAL_CHAIN_ASSIGN=1
      Flags `obj?.field = value` (allowed by some toolchains, illegal
      in strict mode runtimes). When the flag is unset, the pattern
      is silently allowed.

  Project-local opt-in: list the flag suffix under
  `experimental_detectors` in `.claude/mutation-allowlist.yml`.

Source-map remapping (plan item 389):

  When the file under analysis is a transpiled artifact (`*.min.js`,
  `dist/*`, `build/*`, `.next/*`) and a sibling `*.map` source map is
  present, the hook decodes the base64 VLQ mappings and re-projects
  every Match position back to the original source file. Findings
  surface with the original `src/...` path and line, not the bundled
  output. The remap is best-effort: failures fall back silently to
  the transpiled coordinates. See `scripts/mutation_source_map.py`.

Suppression budget (plan item 392):

  Per-project budget config at
  `<project-root>/.claude/mutation-budget.{yml,yaml,json}`. The
  budget caps total `@claude-allow-mutation` markers, per-detector
  marker counts, and optionally requires justification trailers
  (`-- <reason>`). Run `python3 scripts/mutation_budget_check.py`
  in CI to enforce. Schema:
  `~/.claude/schemas/mutation-budget.schema.json`.

Detector tuning report (plan item 393):

  `scripts/detector_tuning_report.py` aggregates telemetry from the
  hook audit log, OpenTelemetry span dumps, or SARIF documents and
  ranks detectors by allow ratio, latency p95, and average
  confidence. Quarterly cadence: archive under
  `docs/telemetry/<YYYY-Q#>.md`.

TypeScript Project Service (plan item 394):

  When `MUTATION_METHOD_TS_PROJECT_SERVICE=1` and Node.js plus the
  `typescript` package (>= 5.6) are present, the hook spawns a
  long-running Node helper (`scripts/ts_project_service.js`) that
  resolves receiver types at each mutation site:

    - `readonly T[]`, `ReadonlyArray<T>`, `ReadonlyMap`,
      `ReadonlySet` -> finding dropped (compiler already rejects).
    - `URLSearchParams`, `Headers`, `FormData` -> finding kept.
    - `TypedArray` subtypes -> hot-path semantics regardless of
      directory.

  Latency budget: 200ms per query, 5000ms total. Failures fall back
  silently to regex-only analysis.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
    ),
)

try:
    from audit_log import record as _audit
except Exception:  # pragma: no cover

    def _audit(**_fields: Any) -> None:
        return None


from hook_io import block as _hio_block

from mutation_allowlists import (
    JOTAI_CALLBACK_OPENER_PATTERN,
    collect_state_mgmt_receivers,
    collect_svelte_state_raw_receivers,
    hit_uses_receiver,
    is_framework_receiver,
    is_hot_path,
    is_in_state_mgmt_scope,
    is_param_reassign_allowed_name,
    is_state_mgmt_filename,
    skip_extension,
    skip_path,
)
from mutation_detectors_assignments import (
    detect_compound_assignment,
    detect_computed_or_index_assignment,
    detect_delete_operator,
    detect_global_assignment,
    detect_increment_decrement,
    detect_let_could_be_const,
    detect_object_assign_target_mutation,
    detect_object_define_setprototype,
    detect_optional_chain_assignment,
    detect_param_reassignment,
    detect_private_field_assignment,
    detect_property_assignment,
    detect_reflect_mutations,
    detect_static_block_mutation,
    detect_effect_ts_ref_value_assign,
    detect_mobx_observable_outside_action,
    detect_nanostores_computed_write,
    detect_xstate_non_assign_context_write,
    detect_svelte_derived_reassign,
    detect_tanstack_store_state_write,
    detect_vue_shallow_readonly_nested_write,
    detect_symbol_key_assignment,
    filter_matches_in_canonical_static_blocks,
)
from mutation_confidence import (
    TYPED_SUFFIX_HINTS,
    score_finding,
    to_sarif_level,
)
from mutation_detectors_core import (
    Match,
    ast_grep_path,
    detect_lang,
    strip_strings_comments,
)
from mutation_source_map import is_transpiled_path, load_source_map, map_to_original
from mutation_ts_project_service import (
    is_available as ts_ps_available,
    is_enabled as ts_ps_enabled,
    query_receiver_type as ts_ps_query,
    shutdown as ts_ps_shutdown,
)
from mutation_detectors_methods import (
    detect_array_pop_shift_unshift_splice_reverse_fill_copywithin,
    detect_array_push,
    detect_array_sort,
    detect_arraybuffer_transfer,
    detect_atomics_mutations,
    detect_bracket_dispatch,
    detect_dataview_setters,
    detect_date_setters,
    detect_finalization_registry,
    detect_for_await_push_pattern,
    detect_form_data_mutations,
    detect_headers_mutations,
    detect_map_set_collection_mutations,
    detect_map_upsert,
    detect_object_groupby_push,
    detect_proxy_mutating_traps,
    detect_typed_array_mutations,
    detect_uint8_base64_setter,
    detect_uint8array_set_buffer_offset,
    detect_url_search_params_mutations,
    detect_wasm_memory_grow,
    detect_weakref_then_mutate,
)
from suppression import (
    BlockState,
    compute_block_state,
    has_inline_marker,
    has_justification_trailer,
    has_ts_nocheck_directive,
    is_suppressed,
)

from mutation_version import VERSION as _MUTATION_VERSION

VERSION = _MUTATION_VERSION
__version__ = _MUTATION_VERSION
PERF_BUDGET_MS = 200


def _receiver_known(match: Match) -> bool:
    """True when the match has a typed-suffix receiver hint.

    Plan item 266. Drives confidence scoring: a typed receiver
    (`bytesArray.set(...)`) is more likely a real mutation than
    a bare property-style call.
    """
    receiver = match.metadata.get("receiver", "") if match.metadata else ""
    if not receiver:
        return False
    head = receiver.split(".", 1)[0].split("[", 1)[0].strip()
    return any(head.endswith(suffix) for suffix in TYPED_SUFFIX_HINTS)


def _enrich_with_confidence(matches: list[Match], file_path: str) -> list[Match]:
    """Return a new list with each match's metadata['confidence'] re-scored.

    Plan item 266. Replaces the static `confidence` set by the detector
    with a 1-10 score from `mutation_confidence.score_finding`. Matches
    are rebuilt via dataclasses.replace because Match is frozen.
    """
    import dataclasses

    enriched: list[Match] = []
    for m in matches:
        ast_confirmed = bool(m.node_type)
        score = score_finding(
            m.detector,
            ast_confirmed=ast_confirmed,
            receiver_known=_receiver_known(m),
            file_path=file_path,
        )
        new_metadata = {**(m.metadata or {}), "confidence": str(score)}
        enriched.append(dataclasses.replace(m, metadata=new_metadata))
    return enriched


def _concise_mode() -> bool:
    """Plan item 251: `MUTATION_METHOD_CONCISE=1` strips fix suggestions
    and the "how to suppress" footer from the block message, leaving only
    title lines. Useful when stderr is harvested by a tool that reformats
    findings on its own.
    """
    return (os.environ.get("MUTATION_METHOD_CONCISE") or "").strip() == "1"


def _debug_mode() -> bool:
    """Plan item 252: `MUTATION_METHOD_DEBUG=1` emits internal state to
    stderr: detectors fired, suppressions applied, allowlist short-circuits,
    AST availability. Off by default.
    """
    return (os.environ.get("MUTATION_METHOD_DEBUG") or "").strip() == "1"


def _profile_mode() -> bool:
    """Plan item 247: `MUTATION_METHOD_PROFILE=1` writes a cProfile report
    to `~/.claude/logs/mutation_blocker_profile.txt` for the current
    invocation. Off by default; intended for ad-hoc latency investigations.
    """
    return (os.environ.get("MUTATION_METHOD_PROFILE") or "").strip() == "1"


def _output_format() -> str:
    """Return the configured output format: 'sarif', 'lsp', or 'text'.

    Plan item 221: `MUTATION_METHOD_OUTPUT=sarif` switches stderr block
    rendering to a SARIF 2.1.0 JSON document on stdout.

    Plan item 363: `MUTATION_METHOD_OUTPUT=lsp` emits a JSON array of
    LSP 3.17 `PublishDiagnosticsParams` so editor extensions can ingest
    findings directly. Default 'text' keeps backward compatibility.
    """
    val = (os.environ.get("MUTATION_METHOD_OUTPUT") or "").strip().lower()
    if val == "sarif":
        return "sarif"
    if val == "lsp":
        return "lsp"
    return "text"


def _experimental_enabled(name: str) -> bool:
    """Return True when experimental detector `name` is enabled.

    Plan items 291-293. Detectors gated by the
    `MUTATION_METHOD_EXPERIMENTAL_<NAME>=1` env var are off by default.
    Enables incremental rollout of new detection without breaking
    existing users. The convention is the all-caps detector name with
    underscores (e.g., `OPTIONAL_CHAIN_ASSIGN`).
    """
    var = f"MUTATION_METHOD_EXPERIMENTAL_{name}"
    return (os.environ.get(var) or "").strip() == "1"


def _batch_mode_enabled() -> bool:
    """Return True when batch mode is enabled.

    Plan item 227: `MUTATION_METHOD_BATCH_MODE=1` makes the hook read
    file paths from stdin (one per line) instead of a JSON tool envelope.
    Used by CI to scan a repository in a single invocation.
    """
    return (os.environ.get("MUTATION_METHOD_BATCH_MODE") or "").strip() == "1"


def _fail_threshold() -> str:
    """Return the configured fail threshold for batch mode.

    Plan item 229. Values: 'error', 'warning', 'note', 'none'. Default 'error'.
    """
    val = (os.environ.get("MUTATION_METHOD_FAIL_THRESHOLD") or "error").strip().lower()
    if val in ("error", "warning", "note", "none"):
        return val
    return "error"


SAMPLE_LINE_CAP = 100
MAX_HITS_PER_FILE = 8
TOP_OF_FILE_SCAN = 10

ALLOW_FILE_MARKER = "@claude-allow-mutation"
ALLOW_LINE_MARKER = "claude-allow-mutation"

PROPERTY_DETECTORS: frozenset[str] = frozenset(
    {
        "property.assignment",
        "property.computed",
        "property.compound",
        "property.compound-index",
        "property.increment",
        "property.increment-prefix",
    }
)


def _normalize_payload(
    tool: str, tool_input: dict[str, Any]
) -> list[tuple[str, str, str, bool]]:
    """Extract (file_path, field_name, text, is_full_file) tuples.

    `is_full_file` distinguishes Write payloads from Edit and MultiEdit
    fragments. The let-could-be-const detector runs only on full-file
    payloads because partial fragments cannot prove a `let` is never
    reassigned later in the file.
    """
    out: list[tuple[str, str, str, bool]] = []
    fp = tool_input.get("file_path", "") or ""
    if tool == "Write":
        c = tool_input.get("content", "")
        if isinstance(c, str):
            out.append((fp, "content", c, True))
    elif tool == "Edit":
        c = tool_input.get("new_string", "")
        if isinstance(c, str):
            out.append((fp, "new_string", c, False))
    elif tool == "MultiEdit":
        edits = tool_input.get("edits", []) or []
        for i, edit in enumerate(edits):
            if isinstance(edit, dict):
                c = edit.get("new_string", "")
                if isinstance(c, str):
                    out.append((fp, f"edits[{i}].new_string", c, False))
    return out


_TYPED_ARRAY_OVERLAP_DETECTORS: frozenset[str] = frozenset(
    {
        "array.fill",
        "array.sort",
        "array.reverse",
        "array.copyWithin",
    }
)


def _detect_all(
    text: str, lang: str | None, file_path: str, is_full_file: bool
) -> list[Match]:
    """Invoke every detector and aggregate matches.

    TypedArray detection is skipped in hot-path directories. The let-const
    detector runs only on full-file Write payloads so partial Edit fragments
    do not produce false positives from missing reassignment context.

    In hot paths, array detectors whose method name overlaps with TypedArray
    prototype (fill, sort, reverse, copyWithin) are also skipped: the receiver
    in a crypto/codec/image file is almost always a TypedArray, and the
    regular array detector cannot tell the difference from the receiver name
    alone. Methods unique to Array (push, pop, shift, unshift, splice) still
    fire so genuine Array misuse in hot paths is caught.
    """
    hot = is_hot_path(file_path)
    matches: list[Match] = []
    matches.extend(detect_array_push(text, lang, file_path))
    array_sort_matches = detect_array_sort(text, lang, file_path)
    array_misc_matches = detect_array_pop_shift_unshift_splice_reverse_fill_copywithin(
        text, lang, file_path
    )
    if hot:
        array_sort_matches = [
            m
            for m in array_sort_matches
            if m.detector not in _TYPED_ARRAY_OVERLAP_DETECTORS
        ]
        array_misc_matches = [
            m
            for m in array_misc_matches
            if m.detector not in _TYPED_ARRAY_OVERLAP_DETECTORS
        ]
    matches.extend(array_sort_matches)
    matches.extend(array_misc_matches)
    matches.extend(detect_bracket_dispatch(text, lang, file_path))
    matches.extend(detect_map_set_collection_mutations(text, lang, file_path))
    if not hot:
        matches.extend(detect_typed_array_mutations(text, lang, file_path))
    matches.extend(detect_date_setters(text, lang, file_path))
    matches.extend(detect_url_search_params_mutations(text, lang, file_path))
    matches.extend(detect_headers_mutations(text, lang, file_path))
    matches.extend(detect_form_data_mutations(text, lang, file_path))
    if not hot:
        matches.extend(detect_dataview_setters(text, lang, file_path))
        matches.extend(detect_uint8array_set_buffer_offset(text, lang, file_path))
    matches.extend(detect_atomics_mutations(text, lang, file_path))
    matches.extend(detect_wasm_memory_grow(text, lang, file_path))
    matches.extend(detect_proxy_mutating_traps(text, lang, file_path))
    matches.extend(detect_weakref_then_mutate(text, lang, file_path))
    matches.extend(detect_finalization_registry(text, lang, file_path))
    matches.extend(detect_for_await_push_pattern(text, lang, file_path))
    if not hot:
        matches.extend(detect_uint8_base64_setter(text, lang, file_path))
    matches.extend(detect_map_upsert(text, lang, file_path))
    matches.extend(detect_arraybuffer_transfer(text, lang, file_path))
    matches.extend(detect_object_groupby_push(text, lang, file_path))
    matches.extend(detect_property_assignment(text, lang, file_path))
    matches.extend(detect_computed_or_index_assignment(text, lang, file_path))
    matches.extend(detect_compound_assignment(text, lang, file_path))
    matches.extend(detect_increment_decrement(text, lang, file_path))
    matches.extend(detect_object_assign_target_mutation(text, lang, file_path))
    matches.extend(detect_object_define_setprototype(text, lang, file_path))
    matches.extend(detect_reflect_mutations(text, lang, file_path))
    matches.extend(detect_delete_operator(text, lang, file_path))
    matches.extend(detect_global_assignment(text, lang, file_path))
    matches.extend(detect_param_reassignment(text, lang, file_path))
    matches.extend(detect_private_field_assignment(text, lang, file_path))
    matches.extend(detect_symbol_key_assignment(text, lang, file_path))
    matches.extend(detect_static_block_mutation(text, lang, file_path))
    matches.extend(detect_effect_ts_ref_value_assign(text, lang, file_path))
    matches.extend(detect_mobx_observable_outside_action(text, lang, file_path))
    matches.extend(detect_nanostores_computed_write(text, lang, file_path))
    matches.extend(detect_svelte_derived_reassign(text, lang, file_path))
    matches.extend(detect_tanstack_store_state_write(text, lang, file_path))
    matches.extend(detect_vue_shallow_readonly_nested_write(text, lang, file_path))
    matches.extend(detect_xstate_non_assign_context_write(text, lang, file_path))
    if is_full_file:
        matches.extend(detect_let_could_be_const(text, lang, file_path))
    if _experimental_enabled("OPTIONAL_CHAIN_ASSIGN"):
        matches.extend(detect_optional_chain_assignment(text, lang, file_path))
    matches = filter_matches_in_canonical_static_blocks(matches, text)
    return matches


def _file_marker_active(lines: list[str]) -> bool:
    """Return True when a top-of-file allow marker exists with justification.

    Without a justification trailer the marker is ignored (per plan item 96):
    `// @claude-allow-mutation` alone does not bypass the hook; the writer
    must append `-- <reason>` to make the suppression auditable.
    """
    seen = 0
    for line in lines:
        if seen >= TOP_OF_FILE_SCAN:
            break
        if not line.strip():
            continue
        seen += 1
        if has_inline_marker(line, ALLOW_FILE_MARKER) and has_justification_trailer(
            line
        ):
            return True
    return False


def _is_line_only_marker(line: str) -> bool:
    """True when the line carries the bare line-marker without the file `@` form.

    `ALLOW_LINE_MARKER` is a substring of `ALLOW_FILE_MARKER`, so a naive
    `has_inline_marker(line, ALLOW_LINE_MARKER)` returns True for both. This
    helper excludes lines that carry the file marker so a stray
    `// @claude-allow-mutation -- too late` past the top-of-file scan does
    not silently suppress the next line as if it were a line marker.
    """
    return (
        has_inline_marker(line, ALLOW_LINE_MARKER)
        and not has_inline_marker(line, ALLOW_FILE_MARKER)
        and has_justification_trailer(line)
    )


def _line_allow_marker_active(lines: list[str], idx: int) -> bool:
    """Return True when the per-line allow marker is present with justification.

    The marker may live on the offending line or on the line directly above,
    matching the convention used by `eslint-disable-line` and
    `eslint-disable-next-line`.
    """
    if idx < 0 or idx >= len(lines):
        return False
    if _is_line_only_marker(lines[idx]):
        return True
    if idx > 0 and _is_line_only_marker(lines[idx - 1]):
        return True
    return False


_YJS_VAR_DECL_PATTERN = __import__("re").compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*[=:]\s*new\s+Y\.(?:Array|Map|Text|XmlElement|XmlFragment|XmlText|Doc)\b"
)


def _is_inside_state_mgmt_scope(
    lines: list[str],
    hit_idx: int,
    file_path: str,
) -> tuple[bool, str | None]:
    """Check state-management scope around a detector hit.

    Two strategies are combined so callback-style and declaration-style
    libraries are both covered:

    1. Brace-balanced scope. Walks back up to 60 lines looking for a line
       that matches a callback-style state-mgmt opener (Immer produce,
       Mutative create, Redux Toolkit createSlice, Pinia defineStore,
       Vuex mutations, MobX action, Zustand set+produce). If the brace
       depth between the opener and the hit is positive, the hit is inside
       the callback body.
    2. Receiver-name scope. Scans the whole text for Yjs declarations
       (`const yArr = new Y.Array()`, etc.) and collects the receiver
       names. If the hit's owner matches any of those names, the mutation
       is on a Yjs CRDT type and is allowed.

    State-mgmt filenames (slice, store, reducer) act as a final fallback.
    """
    state_mgmt_filename = is_state_mgmt_filename(file_path)
    if not lines:
        if state_mgmt_filename:
            return True, "state-mgmt-filename"
        return False, None

    full_text = "\n".join(lines)
    yjs_receivers = {m.group(1) for m in _YJS_VAR_DECL_PATTERN.finditer(full_text)}
    hit_line = lines[hit_idx] if 0 <= hit_idx < len(lines) else ""
    svelte_raw_receivers = collect_svelte_state_raw_receivers(full_text)
    if svelte_raw_receivers and hit_uses_receiver(hit_line, svelte_raw_receivers):
        return False, None
    if yjs_receivers:
        for name in yjs_receivers:
            if name and (f" {name}." in hit_line or hit_line.startswith(f"{name}.")):
                return True, "yjs-crdt"

    receivers_by_lib = collect_state_mgmt_receivers(full_text, file_path)
    for label, names in receivers_by_lib.items():
        if hit_uses_receiver(hit_line, names):
            return True, label

    if hit_line:
        in_scope, scope_label = is_in_state_mgmt_scope(hit_line, file_path)
        if in_scope and scope_label not in {"state-mgmt-filename", "yjs-crdt"}:
            return True, scope_label

    lookback_start = max(0, hit_idx - 60)
    for opener_idx in range(hit_idx - 1, lookback_start - 1, -1):
        opener_line = lines[opener_idx] if 0 <= opener_idx < len(lines) else ""
        if not opener_line:
            continue
        in_scope, scope_label = is_in_state_mgmt_scope(opener_line, file_path)
        is_jotai_callback = bool(JOTAI_CALLBACK_OPENER_PATTERN.search(opener_line))
        if (not in_scope and not is_jotai_callback) or scope_label in {
            "state-mgmt-filename",
            "yjs-crdt",
        }:
            continue
        between = "\n".join(lines[opener_idx : hit_idx + 1])
        masked = strip_strings_comments(between)
        if masked.count("{") - masked.count("}") > 0:
            return True, scope_label or "jotai-atomWithReducer"

    if state_mgmt_filename:
        return True, "state-mgmt-filename"
    return False, None


def _filter_matches(
    matches: list[Match],
    text: str,
    file_path: str,
    block_state: BlockState,
) -> tuple[list[Match], dict[str, int]]:
    """Apply suppression and allowlist filters.

    Returns the surviving matches plus a counter of allow-decision reasons
    so the audit log can record why the hook stayed silent on candidates
    the detectors found but the orchestrator suppressed.
    """
    lines = text.splitlines()
    if _file_marker_active(lines):
        return [], {"file-marker": len(matches)}
    if has_ts_nocheck_directive(lines):
        return [], {"ts-nocheck": len(matches)}

    survived: list[Match] = []
    allow_reasons: dict[str, int] = {}
    for m in matches:
        idx = m.line - 1

        if 0 <= idx < len(lines) and is_suppressed(lines, idx, block_state=block_state):
            allow_reasons["eslint-or-ts-marker"] = (
                allow_reasons.get("eslint-or-ts-marker", 0) + 1
            )
            continue

        if _line_allow_marker_active(lines, idx):
            allow_reasons["claude-allow-mutation"] = (
                allow_reasons.get("claude-allow-mutation", 0) + 1
            )
            continue

        if m.detector == "array.push":
            owner = (m.metadata.get("owner") if m.metadata else "") or ""
            line = lines[idx] if 0 <= idx < len(lines) else ""
            if is_framework_receiver(line, owner):
                allow_reasons["framework-receiver"] = (
                    allow_reasons.get("framework-receiver", 0) + 1
                )
                continue

        if m.detector in PROPERTY_DETECTORS:
            receiver = (m.metadata.get("receiver") if m.metadata else "") or ""
            first_ident = receiver.split(".")[0].split("[")[0].strip()
            if first_ident and is_param_reassign_allowed_name(first_ident):
                allow_reasons["param-allowlist"] = (
                    allow_reasons.get("param-allowlist", 0) + 1
                )
                continue

        if m.detector in {
            "effect-ts.ref-value-assign",
            "mobx.observable-outside-action",
            "nanostores.computed-write",
            "svelte.derived-reassign",
            "tanstack.store-state-write",
            "vue.shallow-readonly-nested-write",
            "xstate.non-assign-context-write",
        }:
            survived.append(m)
            continue

        in_scope, scope_label = _is_inside_state_mgmt_scope(lines, idx, file_path)
        if in_scope:
            key = f"state-mgmt:{scope_label}" if scope_label else "state-mgmt"
            allow_reasons[key] = allow_reasons.get(key, 0) + 1
            continue

        survived.append(m)
    return survived, allow_reasons


_TS_PS_DROPPABLE_KINDS: frozenset[str] = frozenset({"array", "map", "set"})


def _apply_ts_project_service(
    file_path: str, matches: list[Match]
) -> tuple[list[Match], int]:
    """Plan item 394: drop findings whose receiver is provably readonly.

    Queries the TypeScript Project Service for the receiver type at
    each match. When the receiver is `ReadonlyArray<T>`, `ReadonlyMap`,
    or `ReadonlySet`, the compiler already rejects the mutation, so we
    skip the finding to reduce noise. Returns the surviving matches
    plus the count of dropped findings.

    The Project Service is opt-in via `MUTATION_METHOD_TS_PROJECT_SERVICE=1`
    and `node` + `typescript` on PATH. When unavailable, this function
    returns matches unchanged.
    """
    import dataclasses

    if not (ts_ps_enabled() and ts_ps_available()):
        return matches, 0
    if not file_path.endswith((".ts", ".tsx", ".mts", ".cts")):
        return matches, 0
    survived: list[Match] = []
    dropped = 0
    for m in matches:
        info = ts_ps_query(file_path, m.line, max(0, m.col))
        if info is None:
            survived.append(m)
            continue
        new_metadata = {
            **(m.metadata or {}),
            "ts_receiver_type": info.get("type", ""),
            "ts_receiver_kind": info.get("kind", ""),
            "ts_receiver_readonly": "1" if info.get("readonly") else "0",
        }
        if info.get("readonly") and info.get("kind") in _TS_PS_DROPPABLE_KINDS:
            dropped += 1
            continue
        survived.append(dataclasses.replace(m, metadata=new_metadata))
    return survived, dropped


def _remap_via_source_map(
    file_path: str, matches: list[Match]
) -> tuple[str, list[Match]]:
    """Plan item 389: rewrite findings to original source coordinates.

    When the analyzed file is transpiled output (`dist/`, `build/`, `out/`,
    `lib/`, `.next/`, `.nuxt/`) and a sibling `.map` file exists, parse the
    source map and replace each match's `(line, col)` with the original
    source position. The reported file path is replaced with the source
    file referenced by the map.

    Fail open: no map, parse error, or missing segment leaves the match
    untouched. The hook prefers reporting a generated-location finding
    over silently swallowing the mutation.

    Matches from different segments may map back to different original
    files. When that happens, this helper returns the *first* match's
    mapped source file as the canonical path and leaves unmapped matches
    pointing at the generated location.
    """
    import dataclasses

    if not is_transpiled_path(file_path):
        return file_path, matches
    source_map = load_source_map(file_path)
    if source_map is None:
        return file_path, matches

    remapped: list[Match] = []
    canonical_source: str | None = None
    for m in matches:
        mapped = map_to_original(source_map, m.line, m.col)
        if mapped is None:
            remapped.append(m)
            continue
        source_path, orig_line, orig_col = mapped
        if canonical_source is None:
            canonical_source = source_path
        new_metadata = {
            **(m.metadata or {}),
            "generated_file": file_path,
            "generated_line": str(m.line),
            "generated_col": str(m.col),
            "source_file": source_path,
        }
        remapped.append(
            dataclasses.replace(m, line=orig_line, col=orig_col, metadata=new_metadata)
        )
    return canonical_source or file_path, remapped


def _format_findings(file_path: str, matches: list[Match]) -> list[str]:
    """Render block output as one header line per file plus per-match detail."""
    out: list[str] = [f"  - {file_path}:"]
    for m in matches[:MAX_HITS_PER_FILE]:
        excerpt = m.text[:SAMPLE_LINE_CAP]
        out.append(f"      L{m.line}:{m.col} [{m.detector}] {excerpt}")
        if m.fix_hint:
            out.append(f"        fix: {m.fix_hint[:200]}")
    if len(matches) > MAX_HITS_PER_FILE:
        out.append(f"      ... and {len(matches) - MAX_HITS_PER_FILE} more")
    return out


_I18N_CACHE: dict[str, dict[str, Any]] = {}


def _load_i18n(locale: str) -> dict[str, Any]:
    """Load translation bundle for the given locale. Falls back to en.

    Plan item 391. Bundles live under `hooks/i18n/<locale>.json`. The
    resolver tries the exact match, then the base language (e.g. `pt`
    for `pt-BR`), then `en`. Bundles are cached for the process
    lifetime.
    """
    if locale in _I18N_CACHE:
        return _I18N_CACHE[locale]
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [locale]
    if "-" in locale:
        candidates.append(locale.split("-", 1)[0])
    candidates.append("en")
    for cand in candidates:
        path = os.path.join(here, "i18n", f"{cand}.json")
        try:
            with open(path, encoding="utf-8") as fh:
                bundle: dict[str, Any] = json.load(fh)
                _I18N_CACHE[locale] = bundle
                return bundle
        except (OSError, ValueError):
            continue
    _I18N_CACHE[locale] = {}
    return {}


def _build_message(findings: list[str]) -> str:
    locale = os.environ.get("MUTATION_METHOD_LOCALE", "en") or "en"
    bundle = _load_i18n(locale)
    header: str = bundle.get(
        "blocked_header",
        'Blocked: in-place mutation detected. Rule: ~/.claude/rules/code-style.md "Immutability".',
    )
    title = header + "\n" + "\n".join(findings)
    if _concise_mode():
        return title
    fix_header: str = bundle.get("fix_references_header", "Fix references:")
    fix_lines: list[str] = bundle.get("fix_references") or []
    supp_header: str = bundle.get("suppression_header", "Suppression:")
    supp_lines: list[str] = bundle.get("suppression_lines") or []
    byp_header: str = bundle.get("bypass_header", "Bypass envs:")
    byp_lines: list[str] = bundle.get("bypass_lines") or []

    def _format_block(label: str, lines: list[str]) -> str:
        if not lines:
            return ""
        body = "\n".join(f"  - {line}" for line in lines)
        return f"{label}\n{body}"

    sections = [
        _format_block(fix_header, fix_lines),
        _format_block(supp_header, supp_lines),
        _format_block(byp_header, byp_lines),
    ]
    rendered = "\n".join(s for s in sections if s)
    return title + "\n\n" + rendered


def _confidence_to_level(confidence: str) -> str:
    """Map a confidence score to a SARIF level for batch threshold checks."""
    try:
        c = int(confidence)
    except (TypeError, ValueError):
        c = 5
    if c >= 5:
        return "error"
    if c >= 3:
        return "warning"
    return "note"


def _batch_exit_code(findings: list[Any]) -> int:
    """Plan item 229: compute batch exit code from MUTATION_METHOD_FAIL_THRESHOLD.

    threshold='error':   non-zero only on error-level findings.
    threshold='warning': non-zero on warning or error.
    threshold='note':    non-zero on any finding.
    threshold='none':    always 0.
    """
    threshold = _fail_threshold()
    if threshold == "none":
        return 0
    if not findings:
        return 0
    has_error = False
    has_warning = False
    for finding in findings:
        match = finding.match if hasattr(finding, "match") else finding
        level = _confidence_to_level(match.metadata.get("confidence", "5"))
        if level == "error":
            has_error = True
        elif level == "warning":
            has_warning = True
    if threshold == "error":
        return 1 if has_error else 0
    if threshold == "warning":
        return 1 if has_error or has_warning else 0
    return 1


def _read_batch_items() -> list[tuple[str, str, str, bool]]:
    """Plan item 227: batch mode reads file paths from stdin or argv.

    Stdin form (one path per line) is used by CI shell pipelines.
    Argv form is used by pre-commit and other runners that pass file
    paths as positional arguments. The hook reads the file contents and
    treats each as a Write payload (`is_full_file=True`) so full-file
    detectors (`let`-could-be-`const`) fire.
    """
    items: list[tuple[str, str, str, bool]] = []
    paths: list[str] = []
    if len(sys.argv) > 1:
        paths.extend(arg for arg in sys.argv[1:] if arg)
    if not paths:
        try:
            raw = sys.stdin.read()
        except Exception:
            raw = ""
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            paths.append(stripped)
    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        items.append((path, "content", text, True))
    return items


def _handle_cli_flags() -> int | None:
    """Handle introspection flags before the normal hook path.

    Returns an exit code when a flag was consumed, otherwise None so
    main() falls through to its standard payload-reading flow.
    """
    argv = sys.argv[1:]
    if not argv:
        return None
    flag = argv[0]
    if flag in ("--version", "-V"):
        sys.stdout.write(f"mutation-method-blocker {VERSION}\n")
        return 0
    if flag == "--print-detectors":
        import json as _json

        try:
            with open(
                os.path.join(os.path.dirname(__file__), "mutation_fix_suggestions.json"),
                encoding="utf-8",
            ) as fh:
                data = _json.load(fh)
        except OSError as exc:
            sys.stderr.write(f"failed to read detector catalog: {exc}\n")
            return 1
        codes: set[str] = set()
        exact_map = data.get("exact", {}) if isinstance(data, dict) else {}
        for entry in exact_map.values():
            if isinstance(entry, dict) and entry.get("code"):
                codes.add(str(entry["code"]))
        cat_map = data.get("by_category", {}) if isinstance(data, dict) else {}
        for entry in cat_map.values():
            if isinstance(entry, dict) and entry.get("code"):
                codes.add(str(entry["code"]))
        sys.stdout.write(
            _json.dumps({"version": VERSION, "detectors": sorted(codes)}, indent=2)
        )
        sys.stdout.write("\n")
        return 0
    if flag == "--list-allowlists":
        import json as _json

        sys.path.insert(
            0,
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
        )
        try:
            import mutation_allowlists as _aw
        except ImportError as exc:
            sys.stderr.write(f"failed to import allowlists: {exc}\n")
            return 1
        payload: dict[str, object] = {"version": VERSION}
        for name in dir(_aw):
            if name.startswith("_"):
                continue
            value = getattr(_aw, name)
            if isinstance(value, (tuple, list, set, frozenset)) and not callable(value):
                payload[name] = sorted(map(str, value))
        sys.stdout.write(_json.dumps(payload, indent=2))
        sys.stdout.write("\n")
        return 0
    return None


def main() -> int:
    start_ts = time.perf_counter()

    cli_exit = _handle_cli_flags()
    if cli_exit is not None:
        return cli_exit

    if os.environ.get("MUTATION_METHOD_DISABLE") == "1":
        _audit(
            hook="mutation-method-blocker",
            decision="bypass",
            bypass_env="MUTATION_METHOD_DISABLE",
            version=VERSION,
        )
        return 0

    output_format = _output_format()
    batch_mode = _batch_mode_enabled()

    if batch_mode:
        items = _read_batch_items()
        tool = "Batch"
    else:
        try:
            payload = json.load(sys.stdin)
        except Exception:
            return 0
        tool = payload.get("tool_name", "") or ""
        tool_input = payload.get("tool_input", {}) or {}
        items = _normalize_payload(tool, tool_input)
    if not items:
        if output_format == "sarif":
            from sarif_emitter import emit_sarif

            sys.stdout.write(emit_sarif([]))
            sys.stdout.write("\n")
        elif output_format == "lsp":
            from lsp_emitter import emit_lsp

            sys.stdout.write(emit_lsp([]))
            sys.stdout.write("\n")
        return 0

    ast_used = ast_grep_path() is not None
    findings: list[str] = []
    sarif_findings: list[Any] = []
    lsp_findings: list[Any] = []
    detector_counts: dict[str, int] = {}
    allow_counts: dict[str, int] = {}
    files_scanned = 0
    confidence_max = 0

    for path, _field, text, is_full_file in items:
        if skip_extension(path) or skip_path(path):
            continue
        files_scanned += 1
        lang = detect_lang(path)
        block_state = compute_block_state(text.splitlines())
        matches = _detect_all(text, lang, path, is_full_file)
        survived, reasons = _filter_matches(matches, text, path, block_state)
        for k, v in reasons.items():
            allow_counts[k] = allow_counts.get(k, 0) + v
        if not survived:
            continue
        survived = _enrich_with_confidence(survived, path)
        survived, ts_dropped = _apply_ts_project_service(path, survived)
        if ts_dropped:
            allow_counts["ts-readonly"] = (
                allow_counts.get("ts-readonly", 0) + ts_dropped
            )
        if not survived:
            continue
        for m in survived:
            detector_counts[m.detector] = detector_counts.get(m.detector, 0) + 1
            try:
                confidence_max = max(
                    confidence_max, int(m.metadata.get("confidence", "0"))
                )
            except (TypeError, ValueError):
                pass
        report_path, survived = _remap_via_source_map(path, survived)
        if output_format == "sarif":
            from sarif_emitter import Finding

            sarif_findings.extend(Finding(report_path, m) for m in survived)
        elif output_format == "lsp":
            from lsp_emitter import Finding as LspFinding

            lsp_findings.extend(LspFinding(report_path, m) for m in survived)
        findings.extend(_format_findings(report_path, survived))

    duration_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)

    if not findings:
        if files_scanned > 0:
            _audit(
                hook="mutation-method-blocker",
                decision="allow",
                tool=tool,
                version=VERSION,
                duration_ms=duration_ms,
                ast_used=ast_used,
                files_scanned=files_scanned,
                allow_reasons=",".join(
                    f"{k}:{v}" for k, v in sorted(allow_counts.items())
                )
                or None,
            )
        if duration_ms > PERF_BUDGET_MS:
            _audit(
                hook="mutation-method-blocker",
                decision="warn",
                reason="perf-budget-exceeded",
                duration_ms=duration_ms,
                version=VERSION,
                files_scanned=files_scanned,
            )
        if output_format == "sarif":
            from sarif_emitter import emit_sarif

            sys.stdout.write(emit_sarif([]))
            sys.stdout.write("\n")
        elif output_format == "lsp":
            from lsp_emitter import emit_lsp

            sys.stdout.write(emit_lsp([]))
            sys.stdout.write("\n")
        return 0

    if output_format == "sarif":
        from sarif_emitter import emit_sarif

        sys.stdout.write(emit_sarif(sarif_findings))
        sys.stdout.write("\n")
        sys.stdout.flush()
        sys.stderr.write(_build_message(findings))
        sys.stderr.write("\n")
        if batch_mode:
            return _batch_exit_code(sarif_findings)
        return 2

    if output_format == "lsp":
        from lsp_emitter import emit_lsp

        sys.stdout.write(emit_lsp(lsp_findings))
        sys.stdout.write("\n")
        sys.stdout.flush()
        sys.stderr.write(_build_message(findings))
        sys.stderr.write("\n")
        if batch_mode:
            return _batch_exit_code(lsp_findings)
        return 2

    message = _build_message(findings)

    detector_summary = ",".join(
        f"{k}:{v}" for k, v in sorted(detector_counts.items())[:12]
    )
    total_hits = sum(detector_counts.values())
    _audit(
        hook="mutation-method-blocker",
        decision="block",
        tool=tool,
        reason=f"in-place mutation ({total_hits} hits across {len(detector_counts)} detectors)",
        version=VERSION,
        duration_ms=duration_ms,
        ast_used=ast_used,
        detector=detector_summary,
        files_scanned=files_scanned,
        command_excerpt=" | ".join(findings)[:240] if findings else None,
        confidence_score=confidence_max if confidence_max > 0 else None,
        sarif_level=to_sarif_level(confidence_max) if confidence_max > 0 else None,
    )

    if duration_ms > PERF_BUDGET_MS:
        _audit(
            hook="mutation-method-blocker",
            decision="warn",
            reason="perf-budget-exceeded",
            duration_ms=duration_ms,
            version=VERSION,
            files_scanned=files_scanned,
        )

    return _hio_block(message)


def _entrypoint() -> int:
    """Wraps `main()` so `MUTATION_METHOD_PROFILE=1` can wrap it in cProfile.

    Plan item 247. The profile report lands in
    `~/.claude/logs/mutation_blocker_profile.txt` and is overwritten on
    every invocation. Off by default.
    """
    try:
        if not _profile_mode():
            return main()
        import cProfile
        import pstats

        profiler = cProfile.Profile()
        code = profiler.runcall(main)
        log_dir = os.path.join(os.path.expanduser("~"), ".claude", "logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
            with open(
                os.path.join(log_dir, "mutation_blocker_profile.txt"),
                "w",
                encoding="utf-8",
            ) as fh:
                stats = pstats.Stats(profiler, stream=fh).sort_stats("cumulative")
                stats.print_stats(30)
        except OSError:
            pass
        return code
    finally:
        ts_ps_shutdown()


if __name__ == "__main__":
    sys.exit(_entrypoint())
