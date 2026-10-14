from __future__ import annotations

import re

from .mutation_detectors_core import Match
from .mutation_scan_helpers import (
    ASSIGN_OP_ALTERNATION,
    NamedWriteSpec,
    collect_names,
    iter_masked_lines,
    make_match,
    name_alternation,
    scan_named_writes,
)

SVELTE_DERIVED_DECL_PATTERN = re.compile(
    r"\b(?:let|const|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*(?::\s*[^=]+)?\s*=\s*\$derived\s*[(<]"
)

EFFECT_TS_REF_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*(?::\s*[^=]+)?\s*=\s*"
    r"(?:yield\*?\s+)?"
    r"(?:Ref|SubscriptionRef|SynchronizedRef)\.make\s*\("
)

NANOSTORES_COMPUTED_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*(?::\s*[^=]+)?\s*=\s*computed\s*\("
)

TANSTACK_STORE_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*(?::\s*[^=]+)?\s*=\s*"
    r"(?:new\s+Store\s*\(|createStore\s*\()"
)

VUE_SHALLOW_READONLY_DECL_PATTERN = re.compile(
    r"\b(?:let|const|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*(?::\s*[^=]+)?\s*=\s*shallowReadonly\s*\("
)

RECOIL_IMPORT_LINE_PATTERN = re.compile(r"^\s*import\b[^;]*\bfrom\s+['\"]recoil['\"]")

_EFFECT_IMPORT_PATTERN = re.compile(
    r"['\"](?:effect|@effect/(?:io|core|data|stm)(?:/[\w/-]+)?)['\"]"
)
_NANOSTORES_IMPORT_PATTERN = re.compile(r"['\"]nanostores(?:/[\w/-]+)?['\"]")
_TANSTACK_IMPORT_PATTERN = re.compile(
    r"['\"]@tanstack/(?:store|react-store|solid-store)['\"]"
)
_NESTED_WRITE_MIN_ACCESSES = 2

_SVELTE_FIX = (
    "`$derived(...)` bindings are read-only. Reassigning them throws "
    "`state_unsafe_mutation` at runtime. Move the source of truth into a "
    "`$state(...)` binding and let `$derived` recompute, or wrap the "
    "computation in a function. See "
    "https://svelte.dev/docs/svelte/$derived for the reactive contract."
)
_EFFECT_TS_FIX = (
    "Effect-TS Ref bindings have no `.value` property. Updates go "
    "through `Ref.update`, `Ref.set`, or `Ref.modify` and must be "
    "`yield*`-ed inside an `Effect.gen` generator: "
    "`yield* Ref.set(ref, next)`. See "
    "https://effect.website/docs/state-management/ref."
)
_NANOSTORES_FIX = (
    "Nanostores computed stores are read-only derived values. Only the "
    "read accessors and subscription methods are public. Mutating "
    "methods such as setKey or the value setter bypass the recompute "
    "contract. Move the source-of-truth into an atom or map binding "
    "and let computed recompute. See "
    "https://github.com/nanostores/nanostores#computed-stores."
)
_TANSTACK_FIX = (
    "TanStack `Store.state` is a read-only snapshot. Direct writes "
    "(`store.state.x = v`) bypass subscribers and break reactivity. "
    "Use `store.setState((prev) => ({ ...prev, x: v }))` so the "
    "subscription system observes the change. See "
    "https://tanstack.com/store/latest/docs/reference/store#setstate."
)
_VUE_FIX = (
    "`shallowReadonly(obj)` only freezes the top level. Nested writes "
    "(`x.a.b = v`) silently mutate the underlying reactive object. Use "
    "`readonly(obj)` for deep immutability, or rebuild the nested branch "
    "with spread (`{ ...x, a: { ...x.a, b: v } }`) and assign the result "
    "to a fresh ref. See https://vuejs.org/api/reactivity-advanced.html#shallowreadonly"
)
_RECOIL_FIX = (
    "Recoil is unmaintained as of 2024. Migrate to Jotai (atom-based, "
    "closest API), Zustand (store-based with simpler boilerplate), or "
    "Nanostores (tiny, framework-agnostic). See "
    "https://github.com/facebookexperimental/Recoil/issues for context "
    "and https://jotai.org/docs/migrations/from-recoil for a "
    "Recoil-to-Jotai mapping."
)


def _name_and_confidence(m: re.Match[str]) -> dict[str, str]:
    return {"name": m.group("name"), "confidence": "4"}


def _name_method_and_confidence(m: re.Match[str]) -> dict[str, str]:
    return {"name": m.group("name"), "method": m.group("method"), "confidence": "4"}


def _name_chain_and_confidence(m: re.Match[str]) -> dict[str, str]:
    return {"name": m.group("name"), "chain": m.group("chain"), "confidence": "4"}


def _is_nested_write(m: re.Match[str], _lineno: int) -> bool:
    chain = m.group("chain")
    return chain.count(".") + chain.count("[") >= _NESTED_WRITE_MIN_ACCESSES


def detect_svelte_derived_reassign(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    derived_names = collect_names(SVELTE_DERIVED_DECL_PATTERN, text)
    if not derived_names:
        return []
    pattern = re.compile(
        r"^(?P<lead>\s*)(?P<name>"
        + name_alternation(derived_names)
        + r")\s*(?P<op>"
        + ASSIGN_OP_ALTERNATION
        + r")"
    )
    hits = (
        (lineno, raw, pattern.match(masked))
        for lineno, raw, masked in iter_masked_lines(text)
        if not SVELTE_DERIVED_DECL_PATTERN.search(masked)
    )
    return [
        make_match(
            "svelte.derived-reassign",
            lineno,
            m.start("name"),
            raw,
            _SVELTE_FIX,
            _name_and_confidence(m),
        )
        for lineno, raw, m in hits
        if m
    ]


def detect_effect_ts_ref_value_assign(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    if "effect" not in text or not _EFFECT_IMPORT_PATTERN.search(text):
        return []
    names = collect_names(EFFECT_TS_REF_DECL_PATTERN, text)
    if not names:
        return []
    pattern = re.compile(
        r"(?<![\w$.])(?P<name>" + name_alternation(names) + r")\.value"
        r"\s*(?P<op>" + ASSIGN_OP_ALTERNATION + r")"
    )
    spec = NamedWriteSpec(
        detector="effect-ts.ref-value-assign",
        pattern=pattern,
        skip_line=EFFECT_TS_REF_DECL_PATTERN,
        fix_hint=_EFFECT_TS_FIX,
        metadata=_name_and_confidence,
    )
    return scan_named_writes(text, spec)


def detect_nanostores_computed_write(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    if "nanostores" not in text or not _NANOSTORES_IMPORT_PATTERN.search(text):
        return []
    names = collect_names(NANOSTORES_COMPUTED_DECL_PATTERN, text)
    if not names:
        return []
    pattern = re.compile(
        r"(?<![\w$.])(?P<name>" + name_alternation(names) + r")\."
        r"(?P<method>set|setKey|notify)\s*\("
    )
    spec = NamedWriteSpec(
        detector="nanostores.computed-write",
        pattern=pattern,
        skip_line=NANOSTORES_COMPUTED_DECL_PATTERN,
        fix_hint=_NANOSTORES_FIX,
        metadata=_name_method_and_confidence,
    )
    return scan_named_writes(text, spec)


def detect_tanstack_store_state_write(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    if "@tanstack/" not in text or not _TANSTACK_IMPORT_PATTERN.search(text):
        return []
    names = collect_names(TANSTACK_STORE_DECL_PATTERN, text)
    if not names:
        return []
    pattern = re.compile(
        r"(?<![\w$.])(?P<name>" + name_alternation(names) + r")\.state"
        r"(?P<chain>(?:\.[a-zA-Z_$][\w$]*|\[[^\]]+\])*)"
        r"\s*(?P<op>" + ASSIGN_OP_ALTERNATION + r")"
    )
    spec = NamedWriteSpec(
        detector="tanstack.store-state-write",
        pattern=pattern,
        skip_line=TANSTACK_STORE_DECL_PATTERN,
        fix_hint=_TANSTACK_FIX,
        metadata=_name_chain_and_confidence,
    )
    return scan_named_writes(text, spec)


def detect_vue_shallow_readonly_nested_write(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    names = collect_names(VUE_SHALLOW_READONLY_DECL_PATTERN, text)
    if not names:
        return []
    pattern = re.compile(
        r"(?<![\w$.])(?P<name>" + name_alternation(names) + r")"
        r"(?P<chain>(?:\.[a-zA-Z_$][\w$]*|\[[^\]]+\])+)"
        r"\s*(?P<op>" + ASSIGN_OP_ALTERNATION + r")"
    )
    spec = NamedWriteSpec(
        detector="vue.shallow-readonly-nested-write",
        pattern=pattern,
        skip_line=VUE_SHALLOW_READONLY_DECL_PATTERN,
        fix_hint=_VUE_FIX,
        metadata=_name_chain_and_confidence,
        accepts=_is_nested_write,
    )
    return scan_named_writes(text, spec)


def detect_recoil_deprecation_pointer(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    if "recoil" not in text:
        return []
    first_import = next(
        (
            (lineno, raw)
            for lineno, raw, _masked in iter_masked_lines(text)
            if RECOIL_IMPORT_LINE_PATTERN.match(raw)
        ),
        None,
    )
    if first_import is None:
        return []
    lineno, raw = first_import
    return [
        make_match(
            "recoil.deprecation-pointer",
            lineno,
            0,
            raw,
            _RECOIL_FIX,
            {"confidence": "1", "severity": "info"},
        )
    ]
