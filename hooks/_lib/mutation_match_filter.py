from __future__ import annotations

import re

from .mutation_allowlists import (
    collect_state_mgmt_receivers,
    collect_svelte_state_raw_receivers,
    hit_uses_receiver,
    is_framework_receiver,
    is_in_state_mgmt_scope,
    is_param_reassign_allowed_name,
    is_state_mgmt_filename,
)
from .mutation_detectors_core import Match, strip_strings_comments
from .mutation_state_patterns import JOTAI_CALLBACK_OPENER_PATTERN
from .suppression import BlockState, has_ts_nocheck_directive, is_suppressed

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

SCOPE_EXEMPT_DETECTORS: frozenset[str] = frozenset(
    {
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
    }
)

OPENER_LOOKBACK_LINES = 60
FILENAME_SCOPE_LABEL = "state-mgmt-filename"
YJS_SCOPE_LABEL = "yjs-crdt"
JOTAI_SCOPE_LABEL = "jotai-atomWithReducer"
_INDIRECT_SCOPE_LABELS = frozenset({FILENAME_SCOPE_LABEL, YJS_SCOPE_LABEL})

_YJS_VAR_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*[=:]\s*new\s+Y\.(?:Array|Map|Text|XmlElement|XmlFragment|XmlText|Doc)\b"
)

ScopeVerdict = tuple[bool, str | None]


def _filename_verdict(file_path: str) -> ScopeVerdict:
    if is_state_mgmt_filename(file_path):
        return True, FILENAME_SCOPE_LABEL
    return False, None


def _uses_yjs_receiver(full_text: str, hit_line: str) -> bool:
    names = {m.group(1) for m in _YJS_VAR_DECL_PATTERN.finditer(full_text)}
    return any(
        name and (f" {name}." in hit_line or hit_line.startswith(f"{name}."))
        for name in names
    )


def _receiver_verdict(
    full_text: str, hit_line: str, file_path: str
) -> ScopeVerdict | None:
    raw_receivers = collect_svelte_state_raw_receivers(full_text)
    if raw_receivers and hit_uses_receiver(hit_line, raw_receivers):
        return False, None
    if _uses_yjs_receiver(full_text, hit_line):
        return True, YJS_SCOPE_LABEL
    receivers_by_lib = collect_state_mgmt_receivers(full_text, file_path)
    label = next(
        (
            lib
            for lib, names in receivers_by_lib.items()
            if hit_uses_receiver(hit_line, names)
        ),
        None,
    )
    return None if label is None else (True, label)


def _same_line_label(hit_line: str, file_path: str) -> str | None:
    if not hit_line:
        return None
    in_scope, label = is_in_state_mgmt_scope(hit_line, file_path)
    if in_scope and label not in _INDIRECT_SCOPE_LABELS:
        return label
    return None


def _opener_label(lines: list[str], opener_idx: int, file_path: str) -> str | None:
    opener_line = lines[opener_idx] if 0 <= opener_idx < len(lines) else ""
    if not opener_line:
        return None
    in_scope, label = is_in_state_mgmt_scope(opener_line, file_path)
    is_jotai_callback = bool(JOTAI_CALLBACK_OPENER_PATTERN.search(opener_line))
    if (not in_scope and not is_jotai_callback) or label in _INDIRECT_SCOPE_LABELS:
        return None
    return label or JOTAI_SCOPE_LABEL


def _enclosing_opener_label(
    lines: list[str], hit_idx: int, file_path: str
) -> str | None:
    lookback_start = max(0, hit_idx - OPENER_LOOKBACK_LINES)
    for opener_idx in range(hit_idx - 1, lookback_start - 1, -1):
        label = _opener_label(lines, opener_idx, file_path)
        if label is None:
            continue
        masked = strip_strings_comments("\n".join(lines[opener_idx : hit_idx + 1]))
        if masked.count("{") - masked.count("}") > 0:
            return label
    return None


def is_inside_state_mgmt_scope(
    lines: list[str], hit_idx: int, file_path: str
) -> ScopeVerdict:
    if not lines:
        return _filename_verdict(file_path)
    hit_line = lines[hit_idx] if 0 <= hit_idx < len(lines) else ""
    verdict = _receiver_verdict("\n".join(lines), hit_line, file_path)
    if verdict is not None:
        return verdict
    label = _same_line_label(hit_line, file_path) or _enclosing_opener_label(
        lines, hit_idx, file_path
    )
    if label is not None:
        return True, label
    return _filename_verdict(file_path)


def _is_framework_push(match: Match, lines: list[str], idx: int) -> bool:
    if match.detector != "array.push":
        return False
    owner = (match.metadata.get("owner") if match.metadata else "") or ""
    line = lines[idx] if 0 <= idx < len(lines) else ""
    return is_framework_receiver(line, owner)


def _is_allowlisted_param_write(match: Match) -> bool:
    if match.detector not in PROPERTY_DETECTORS:
        return False
    receiver = (match.metadata.get("receiver") if match.metadata else "") or ""
    first_ident = receiver.split(".")[0].split("[")[0].strip()
    return bool(first_ident) and is_param_reassign_allowed_name(first_ident)


def _allow_reason(
    match: Match, lines: list[str], file_path: str, block_state: BlockState
) -> str | None:
    idx = match.line - 1
    if 0 <= idx < len(lines) and is_suppressed(
        lines, idx, block_state=block_state, rules=ESLINT_RULES
    ):
        return "eslint-or-ts-marker"
    if _is_framework_push(match, lines, idx):
        return "framework-receiver"
    if _is_allowlisted_param_write(match):
        return "param-allowlist"
    if match.detector in SCOPE_EXEMPT_DETECTORS:
        return None
    in_scope, scope_label = is_inside_state_mgmt_scope(lines, idx, file_path)
    if not in_scope:
        return None
    return f"state-mgmt:{scope_label}" if scope_label else "state-mgmt"


def _count_reasons(reasons: list[str]) -> dict[str, int]:
    return {reason: reasons.count(reason) for reason in dict.fromkeys(reasons)}


def filter_matches(
    matches: list[Match], text: str, file_path: str, block_state: BlockState
) -> tuple[list[Match], dict[str, int]]:
    lines = text.splitlines()
    if has_ts_nocheck_directive(lines):
        return [], {"ts-nocheck": len(matches)}
    verdicts = [(m, _allow_reason(m, lines, file_path, block_state)) for m in matches]
    survived = [m for m, reason in verdicts if reason is None]
    return survived, _count_reasons([r for _m, r in verdicts if r is not None])
