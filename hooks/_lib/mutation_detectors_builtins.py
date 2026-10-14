from __future__ import annotations

import re

from .mutation_detectors_core import Match
from .mutation_fix_lookup import tc39_stage_filter
from .mutation_scan_helpers import (
    NamedWriteSpec,
    collect_names,
    iter_masked_lines,
    make_match,
    name_alternation,
    scan_named_writes,
)

OBJECT_ASSIGN_PATTERN = re.compile(r"\bObject\.assign\s*\(")

OBJECT_DEFINE_PROPERTY_PATTERN = re.compile(r"\bObject\.defineProperty\s*\(")
OBJECT_DEFINE_PROPERTIES_PATTERN = re.compile(r"\bObject\.defineProperties\s*\(")
OBJECT_SET_PROTOTYPE_OF_PATTERN = re.compile(r"\bObject\.setPrototypeOf\s*\(")

REFLECT_SET_PATTERN = re.compile(r"\bReflect\.set\s*\(")
REFLECT_DELETE_PROPERTY_PATTERN = re.compile(r"\bReflect\.deleteProperty\s*\(")
REFLECT_DEFINE_PROPERTY_PATTERN = re.compile(r"\bReflect\.defineProperty\s*\(")
REFLECT_SET_PROTOTYPE_OF_PATTERN = re.compile(r"\bReflect\.setPrototypeOf\s*\(")

DELETE_PATTERN = re.compile(
    r"\bdelete\s+(?P<target>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*|\s*\[[^\]]+\])+)"
)

GLOBAL_ASSIGN_PATTERN = re.compile(
    r"\b(?:globalThis|process\.env)\.[a-zA-Z_$][\w$]*\s*=(?!=)"
)

NEW_INSTANCE_TARGETS = re.compile(
    r"^\s*\{\s*\}|\bnew\s+Object\s*\(\s*\)|^\s*Object\.create\s*\("
)

ASYNC_ITERATOR_DECL_PATTERN = re.compile(
    r"(?:\b(?:const|let|var)\s+|[(,]\s*)"
    r"(?P<name>[a-zA-Z_$][\w$]*)\s*"
    r":\s*AsyncIterator(?:Object)?\b"
)
ASYNC_ITERATOR_SYMBOL_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*="
    r"\s*[a-zA-Z_$][\w$]*\s*\[\s*Symbol\.asyncIterator\s*\]\s*\(\s*\)"
)

_EXCERPT_ARG_LIMIT = 60
_ASYNC_ITERATOR_MAX_STAGE = 3

_OBJECT_ASSIGN_FIX = (
    "`Object.assign(target, source)` mutates `target`. Use `Object.assign({}, target, source)` "
    "or `{ ...target, ...source }` to produce a new object. When the target is dynamic, "
    "wrap with a fresh `{}` literal first."
)
_DEFINE_FIX = (
    "`Object.defineProperty` rewrites the descriptor. For static shapes declare the property "
    "in the type and the literal. For dynamic computed keys use `{ ...obj, [key]: value }`."
)
_SET_PROTOTYPE_FIX = (
    "`Object.setPrototypeOf` is slow on V8 and breaks shape inference. Use class inheritance, "
    "a factory function, or `Object.create(proto, descriptors)` to produce a fresh object."
)
_DELETE_FIX = (
    "For objects use destructured rest to omit a key: "
    "`const { [key]: _omit, ...rest } = obj; return rest;`. "
    "For arrays use `arr.toSpliced(i, 1)` (ES2023) or `arr.filter((_, j) => j !== i)`."
)
_GLOBAL_FIX = (
    "Mutating `globalThis`, `window`, `process.env`, or similar global objects is module-scope "
    "side effect. Use a typed module export or a configuration object passed by argument. "
    'Rule: ~/.claude/standards/code-style.md "Fundamentals".'
)
_ASYNC_ITERATOR_FIX = (
    "AsyncIterator `.return()` and `.throw()` terminate the iterator "
    "and mutate its internal state. Prefer a `break` inside the "
    "`for await` loop or a try/finally that lets the runtime call the "
    "cleanup hooks. See "
    "https://github.com/tc39/proposal-async-iterator-helpers for the "
    "Stage 3 contract."
)

_DEFINE_DETECTORS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("object.defineProperty", OBJECT_DEFINE_PROPERTY_PATTERN, _DEFINE_FIX),
    ("object.defineProperties", OBJECT_DEFINE_PROPERTIES_PATTERN, _DEFINE_FIX),
    ("object.setPrototypeOf", OBJECT_SET_PROTOTYPE_OF_PATTERN, _SET_PROTOTYPE_FIX),
)

_REFLECT_DETECTORS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "reflect.set",
        REFLECT_SET_PATTERN,
        "Replace `Reflect.set(obj, key, value)` with `{ ...obj, [key]: value }`.",
    ),
    (
        "reflect.deleteProperty",
        REFLECT_DELETE_PROPERTY_PATTERN,
        "Replace `Reflect.deleteProperty(obj, key)` with destructured rest: "
        "`const { [key]: _omit, ...rest } = obj`.",
    ),
    (
        "reflect.defineProperty",
        REFLECT_DEFINE_PROPERTY_PATTERN,
        "`Reflect.defineProperty` rewrites the descriptor. Declare the property in the type and "
        "the object literal instead.",
    ),
    (
        "reflect.setPrototypeOf",
        REFLECT_SET_PROTOTYPE_OF_PATTERN,
        "`Reflect.setPrototypeOf` mutates the prototype chain at runtime. Use class inheritance "
        "or a factory function.",
    ),
)


def _extract_first_arg(masked: str, paren_idx: int) -> str | None:
    depth = 0
    for i in range(paren_idx, len(masked)):
        ch = masked[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return masked[paren_idx + 1 : i].strip()
        elif ch == "," and depth == 1:
            return masked[paren_idx + 1 : i].strip()
    return None


def _assign_target(masked: str, start: int) -> str | None:
    paren_idx = masked.find("(", start)
    return _extract_first_arg(masked, paren_idx) if paren_idx >= 0 else None


def _assign_hit(lineno: int, raw: str, masked: str, start: int) -> Match | None:
    first = _assign_target(masked, start)
    if first is None or NEW_INSTANCE_TARGETS.match(first):
        return None
    return make_match(
        "object.assign",
        lineno,
        start,
        raw,
        _OBJECT_ASSIGN_FIX,
        {"first_arg": first[:_EXCERPT_ARG_LIMIT]},
    )


def detect_object_assign_target_mutation(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    hits = (
        _assign_hit(lineno, raw, masked, m.start())
        for lineno, raw, masked in iter_masked_lines(text)
        for m in OBJECT_ASSIGN_PATTERN.finditer(masked)
    )
    return [hit for hit in hits if hit is not None]


def _scan_table(
    text: str, table: tuple[tuple[str, re.Pattern[str], str], ...]
) -> list[Match]:
    return [
        make_match(detector, lineno, m.start(), raw, fix_hint)
        for lineno, raw, masked in iter_masked_lines(text)
        for detector, pattern, fix_hint in table
        for m in pattern.finditer(masked)
    ]


def detect_object_define_setprototype(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return _scan_table(text, _DEFINE_DETECTORS)


def detect_reflect_mutations(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return _scan_table(text, _REFLECT_DETECTORS)


def detect_delete_operator(text: str, lang: str | None, file_path: str) -> list[Match]:
    return [
        make_match(
            "delete-operator",
            lineno,
            m.start(),
            raw,
            _DELETE_FIX,
            {"target": (m.group("target") or "").strip()[:_EXCERPT_ARG_LIMIT]},
        )
        for lineno, raw, masked in iter_masked_lines(text)
        for m in DELETE_PATTERN.finditer(masked)
    ]


def detect_global_assignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return [
        make_match("global.assignment", lineno, m.start(), raw, _GLOBAL_FIX)
        for lineno, raw, masked in iter_masked_lines(text)
        for m in GLOBAL_ASSIGN_PATTERN.finditer(masked)
    ]


def _async_iterator_names(text: str) -> frozenset[str]:
    return collect_names(ASYNC_ITERATOR_DECL_PATTERN, text) | collect_names(
        ASYNC_ITERATOR_SYMBOL_DECL_PATTERN, text
    )


def _async_iterator_metadata(m: re.Match[str]) -> dict[str, str]:
    return {
        "name": m.group("name"),
        "method": m.group("method"),
        "confidence": "3",
        "tc39_stage": "3",
    }


def detect_async_iterator_return_throw(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    if tc39_stage_filter() > _ASYNC_ITERATOR_MAX_STAGE:
        return []
    if "AsyncIterator" not in text and "Symbol.asyncIterator" not in text:
        return []
    names = _async_iterator_names(text)
    if not names:
        return []
    pattern = re.compile(
        r"(?<![\w$.])(?P<name>" + name_alternation(names) + r")\."
        r"(?P<method>return|throw)\s*\("
    )
    spec = NamedWriteSpec(
        detector="async-iterator.return-throw",
        pattern=pattern,
        skip_line=None,
        fix_hint=_ASYNC_ITERATOR_FIX,
        metadata=_async_iterator_metadata,
    )
    return scan_named_writes(text, spec)
