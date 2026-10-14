#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from _lib.audit_log import record as _audit
except Exception:  # pragma: no cover

    def _audit(**_fields: Any) -> None:
        return None


from _lib.mutation_allowlists import (
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
from _lib.mutation_detectors_assignments import (
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
    detect_async_iterator_return_throw,
    detect_automerge_direct_mutation,
    detect_effect_ts_ref_value_assign,
    detect_mobx_observable_outside_action,
    detect_nanostores_computed_write,
    detect_recoil_deprecation_pointer,
    detect_xstate_non_assign_context_write,
    detect_yjs_mutation_outside_transact,
    detect_svelte_derived_reassign,
    detect_tanstack_store_state_write,
    detect_vue_shallow_readonly_nested_write,
    detect_symbol_key_assignment,
    filter_matches_in_canonical_static_blocks,
)
from _lib.mutation_confidence import (
    TYPED_SUFFIX_HINTS,
    score_finding,
    to_sarif_level,
)
from _lib.mutation_detectors_core import (
    Match,
    ast_grep_path,
    detect_lang,
    strip_strings_comments,
)
from _lib.mutation_source_map import (
    is_transpiled_path,
    load_source_map,
    map_to_original,
)
from _lib.mutation_detectors_methods import (
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
from _lib.suppression import (
    BlockState,
    compute_block_state,
    has_ts_nocheck_directive,
    is_suppressed,
)

from _lib.mutation_version import VERSION as _MUTATION_VERSION

VERSION = _MUTATION_VERSION
__version__ = _MUTATION_VERSION
PERF_BUDGET_MS = 200

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload, tool_input_of  # noqa: E402


def _receiver_known(match: Match) -> bool:
    receiver = match.metadata.get("receiver", "") if match.metadata else ""
    if not receiver:
        return False
    head = receiver.split(".", 1)[0].split("[", 1)[0].strip()
    return any(head.endswith(suffix) for suffix in TYPED_SUFFIX_HINTS)


def _enrich_with_confidence(matches: list[Match], file_path: str) -> list[Match]:
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
    return (os.environ.get("MUTATION_METHOD_CONCISE") or "").strip() == "1"


def _profile_mode() -> bool:
    return (os.environ.get("MUTATION_METHOD_PROFILE") or "").strip() == "1"


def _experimental_enabled(name: str) -> bool:
    var = f"MUTATION_METHOD_EXPERIMENTAL_{name}"
    return (os.environ.get(var) or "").strip() == "1"


def _batch_mode_enabled() -> bool:
    if sys.argv[1:2] == [BATCH_FLAG]:
        return True
    return (os.environ.get("MUTATION_METHOD_BATCH_MODE") or "").strip() == "1"


BATCH_FLAG = "--batch"

SAMPLE_LINE_CAP = 100
MAX_HITS_PER_FILE = 8
ESLINT_RULES = frozenset(
    {"functional/immutable-data", "fp/no-mutating-methods", "no-param-reassign"}
)

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
    matches.extend(detect_async_iterator_return_throw(text, lang, file_path))
    matches.extend(detect_automerge_direct_mutation(text, lang, file_path))
    matches.extend(detect_effect_ts_ref_value_assign(text, lang, file_path))
    matches.extend(detect_mobx_observable_outside_action(text, lang, file_path))
    matches.extend(detect_nanostores_computed_write(text, lang, file_path))
    matches.extend(detect_recoil_deprecation_pointer(text, lang, file_path))
    matches.extend(detect_svelte_derived_reassign(text, lang, file_path))
    matches.extend(detect_tanstack_store_state_write(text, lang, file_path))
    matches.extend(detect_vue_shallow_readonly_nested_write(text, lang, file_path))
    matches.extend(detect_xstate_non_assign_context_write(text, lang, file_path))
    matches.extend(detect_yjs_mutation_outside_transact(text, lang, file_path))
    if is_full_file:
        matches.extend(detect_let_could_be_const(text, lang, file_path))
    if _experimental_enabled("OPTIONAL_CHAIN_ASSIGN"):
        matches.extend(detect_optional_chain_assignment(text, lang, file_path))
    matches = filter_matches_in_canonical_static_blocks(matches, text)
    return matches


_YJS_VAR_DECL_PATTERN = __import__("re").compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*[=:]\s*new\s+Y\.(?:Array|Map|Text|XmlElement|XmlFragment|XmlText|Doc)\b"
)


def _is_inside_state_mgmt_scope(
    lines: list[str],
    hit_idx: int,
    file_path: str,
) -> tuple[bool, str | None]:
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
    lines = text.splitlines()
    if has_ts_nocheck_directive(lines):
        return [], {"ts-nocheck": len(matches)}

    survived: list[Match] = []
    allow_reasons: dict[str, int] = {}
    for m in matches:
        idx = m.line - 1

        if 0 <= idx < len(lines) and is_suppressed(
            lines, idx, block_state=block_state, rules=ESLINT_RULES
        ):
            allow_reasons["eslint-or-ts-marker"] = (
                allow_reasons.get("eslint-or-ts-marker", 0) + 1
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
            "async-iterator.return-throw",
            "automerge.direct-mutation",
            "effect-ts.ref-value-assign",
            "mobx.observable-outside-action",
            "nanostores.computed-write",
            "recoil.deprecation-pointer",
            "svelte.derived-reassign",
            "tanstack.store-state-write",
            "vue.shallow-readonly-nested-write",
            "xstate.non-assign-context-write",
            "yjs.mutation-outside-transact",
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


def _remap_via_source_map(
    file_path: str, matches: list[Match]
) -> tuple[str, list[Match]]:
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


def _deny(reason: str) -> int:
    if not reason:
        return 2
    print(reason, file=sys.stderr)
    body = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    try:
        sys.stdout.write(json.dumps(body, ensure_ascii=False))
        sys.stdout.flush()
    except (OSError, TypeError, ValueError) as error:
        sys.stderr.write(f"mutation-method-blocker: decision write failed: {error}\n")
    return 2


def _read_batch_items() -> list[tuple[str, str, str, bool]]:
    items: list[tuple[str, str, str, bool]] = []
    paths: list[str] = []
    if len(sys.argv) > 1:
        paths.extend(arg for arg in sys.argv[1:] if arg and arg != BATCH_FLAG)
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
                os.path.join(
                    os.path.dirname(__file__), "mutation_fix_suggestions.json"
                ),
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

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            from _lib import mutation_allowlists as _aw
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
    return None  # pragma: no cover


from _lib.hook_profile import should_run  # noqa: E402


def main() -> int:
    if not should_run("mutation-method-blocker"):
        sys.exit(0)
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
    if is_bypassed("mutation-method-blocker"):
        return 0

    batch_mode = _batch_mode_enabled()

    if batch_mode:
        items = _read_batch_items()
        tool = "Batch"
    else:
        payload = read_hook_payload("mutation-method-blocker")
        tool = str(payload.get("tool_name") or "")
        tool_input = tool_input_of(payload)
        items = _normalize_payload(tool, tool_input)
    if not items:
        return 0

    ast_used = ast_grep_path() is not None
    findings: list[str] = []
    detector_counts: dict[str, int] = {}
    allow_counts: dict[str, int] = {}
    files_scanned = 0
    confidence_max = 0

    for path, _field, text, is_full_file in items:
        if skip_extension(path) or skip_path(path):
            continue
        files_scanned += 1
        lang = detect_lang(path)
        block_state = compute_block_state(text.splitlines(), rules=ESLINT_RULES)
        matches = _detect_all(text, lang, path, is_full_file)
        survived, reasons = _filter_matches(matches, text, path, block_state)
        for k, v in reasons.items():
            allow_counts[k] = allow_counts.get(k, 0) + v
        if not survived:
            continue
        survived = _enrich_with_confidence(survived, path)
        for m in survived:
            detector_counts[m.detector] = detector_counts.get(m.detector, 0) + 1
            raw_confidence = str(m.metadata.get("confidence", "0"))
            if raw_confidence.isdigit():
                confidence_max = max(confidence_max, int(raw_confidence))
        report_path, survived = _remap_via_source_map(path, survived)
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
        return 0

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

    return _deny(message)


def _entrypoint() -> int:
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
    except OSError as error:
        sys.stderr.write(f"mutation-method-blocker: profile write failed: {error}\n")
    return code


if __name__ == "__main__":
    sys.exit(_entrypoint())
