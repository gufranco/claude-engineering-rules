from __future__ import annotations

import re
from collections.abc import Callable

from .mutation_allowlists import is_dom_assignment, is_dom_receiver
from .mutation_detectors_core import Match
from .mutation_scan_helpers import iter_masked_lines as _iter_lines
from .mutation_scan_helpers import looks_like_declaration as _looks_like_declaration
from .mutation_scan_helpers import make_match as _make_match

PROPERTY_ASSIGN_PATTERN = re.compile(
    r"(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*)\s*\.(?P<prop>[a-zA-Z_$][\w$]*)\s*(?P<op>=)(?!=)"
)

COMPUTED_PROPERTY_PATTERN = re.compile(
    r"(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*)\s*\[\s*(?P<key>[^\]]+?)\s*\]\s*(?P<op>=)(?!=)"
)

COMPOUND_OPS: tuple[str, ...] = (
    r"\+=",
    r"-=",
    r"\*\*=",
    r"\*=",
    r"/=",
    r"%=",
    r"<<=",
    r">>>=",
    r">>=",
    r"&&=",
    r"\|\|=",
    r"\?\?=",
    r"&=",
    r"\|=",
    r"\^=",
)

COMPOUND_PATTERN = re.compile(
    r"(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)+)\s*(?P<op>"
    + "|".join(COMPOUND_OPS)
    + r")"
)

COMPOUND_INDEX_PATTERN = re.compile(
    r"(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*\s*\[[^\]]+\])\s*(?P<op>"
    + "|".join(COMPOUND_OPS)
    + r")"
)

UPDATE_POSTFIX_PATTERN = re.compile(
    r"(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)+)\s*(?P<op>\+\+|--)"
)

UPDATE_PREFIX_PATTERN = re.compile(
    r"(?P<op>\+\+|--)\s*(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)+)"
)

OPTIONAL_CHAIN_ASSIGN_PATTERN = re.compile(
    r"(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*)\s*\?\.(?P<prop>[a-zA-Z_$][\w$]*)\s*(?P<op>=)(?!=)"
)

PRIVATE_FIELD_ASSIGN_PATTERN = re.compile(
    r"(?P<receiver>(?:this|[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*))\."
    r"(?P<field>#[a-zA-Z_$][\w$]*)\s*(?P<op>=(?!=)|\+=|-=|\*\*=|\*=|/=|%=|<<=|>>>=|>>=|&&=|\|\|=|\?\?=|&=|\|=|\^=)"
)

PRIVATE_FIELD_UPDATE_POSTFIX_PATTERN = re.compile(
    r"(?P<receiver>(?:this|[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*))\."
    r"(?P<field>#[a-zA-Z_$][\w$]*)\s*(?P<op>\+\+|--)"
)

PRIVATE_FIELD_UPDATE_PREFIX_PATTERN = re.compile(
    r"(?P<op>\+\+|--)\s*"
    r"(?P<receiver>(?:this|[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*))\."
    r"(?P<field>#[a-zA-Z_$][\w$]*)"
)

SYMBOL_KEY_ASSIGN_PATTERN = re.compile(
    r"(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*)\s*\[\s*"
    r"(?P<key>Symbol\.[a-zA-Z_$][\w$]*|[a-zA-Z_$][\w$]*Symbol|"
    r"[a-zA-Z_$][\w$]*\.[a-zA-Z_$]*[Ss]ymbol[\w$]*)\s*\]\s*(?P<op>=(?!=))"
)

_KEY_EXCERPT_LIMIT = 60

_PROPERTY_FIX = (
    "Replace `obj.prop = value` with `obj = { ...obj, prop: value }` or return a copy. "
    "Mark parameters as `Readonly<T>` to enforce at the type level."
)
_COMPUTED_FIX = (
    "For arrays use `arr.with(i, value)` (ES2023) or `arr.map((v, j) => j === i ? value : v)`. "
    "For objects use `{ ...obj, [key]: value }`."
)
_COMPOUND_FIX = (
    "Compound assignments mutate the receiver. Replace `obj.prop += value` with "
    "`obj = { ...obj, prop: obj.prop + value }` or compute a new value separately."
)
_INCREMENT_FIX = (
    "Increment / decrement on a member mutates the receiver. Replace `obj.prop++` with "
    "`obj = { ...obj, prop: obj.prop + 1 }`."
)
_OPTIONAL_CHAIN_FIX = (
    "Optional-chain assignment is not allowed by the ECMAScript spec. "
    "Replace with an explicit guard: `if (obj) { obj = { ...obj, prop: v } }` "
    "or restructure to avoid the assignment."
)
_PRIVATE_FIELD_FIX = (
    "Private fields are mutable by default. Prefer immutable patterns: "
    "return a new instance from the method that needs to change state, or expose "
    "a `with*` method that constructs a fresh class instance. When mutation is "
    "intentional, confine the mutation to the module that owns the value."
)
_SYMBOL_KEY_FIX = (
    "Symbol-keyed property assignment mutates the receiver. Build a fresh object "
    "with the symbol in the literal: `{ ...obj, [Symbol.iterator]: fn }`. For "
    "classes, declare the symbol property in the class body or in a factory."
)

_PRIVATE_FIELD_DETECTORS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("private-field.assignment", PRIVATE_FIELD_ASSIGN_PATTERN, "="),
    ("private-field.update", PRIVATE_FIELD_UPDATE_POSTFIX_PATTERN, "++"),
    ("private-field.update", PRIVATE_FIELD_UPDATE_PREFIX_PATTERN, "++"),
)


def _split_chain(chain: str) -> tuple[str, str]:
    parent, _, last = chain.rpartition(".")
    return parent, last


def _is_comparison(full: str) -> bool:
    return "==" in full or "===" in full


def _is_dom_chain(chain: str) -> bool:
    parent, last = _split_chain(chain)
    return is_dom_assignment(parent, last)


def _is_dom_index_chain(chain: str) -> bool:
    return is_dom_receiver(chain.split("[", 1)[0].strip())


def _undeclared_lines(text: str) -> list[tuple[int, str, str]]:
    return [
        (lineno, raw, masked)
        for lineno, raw, masked in _iter_lines(text)
        if not _looks_like_declaration(raw, masked)
    ]


def _is_property_write(m: re.Match[str]) -> bool:
    return not is_dom_assignment(m.group("receiver") or "", m.group("prop") or "")


def detect_property_assignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return [
        _make_match(
            "property.assignment",
            lineno,
            m.start(),
            raw,
            _PROPERTY_FIX,
            {"receiver": m.group("receiver") or "", "prop": m.group("prop") or ""},
        )
        for lineno, raw, masked in _undeclared_lines(text)
        for m in PROPERTY_ASSIGN_PATTERN.finditer(masked)
        if _is_property_write(m)
    ]


def detect_computed_or_index_assignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return [
        _make_match(
            "property.computed",
            lineno,
            m.start(),
            raw,
            _COMPUTED_FIX,
            {
                "receiver": m.group("receiver") or "",
                "key": (m.group("key") or "").strip()[:_KEY_EXCERPT_LIMIT],
            },
        )
        for lineno, raw, masked in _undeclared_lines(text)
        for m in COMPUTED_PROPERTY_PATTERN.finditer(masked)
        if not _is_comparison(m.group(0))
        and not is_dom_receiver(m.group("receiver") or "")
    ]


_ChainDetector = tuple[str, re.Pattern[str], Callable[[str], bool]]

_COMPOUND_DETECTORS: tuple[_ChainDetector, ...] = (
    ("property.compound", COMPOUND_PATTERN, _is_dom_chain),
    ("property.compound-index", COMPOUND_INDEX_PATTERN, _is_dom_index_chain),
)
_INCREMENT_DETECTORS: tuple[_ChainDetector, ...] = (
    ("property.increment", UPDATE_POSTFIX_PATTERN, _is_dom_chain),
    ("property.increment-prefix", UPDATE_PREFIX_PATTERN, _is_dom_chain),
)


def _chain_hits(
    line: tuple[int, str, str], chain_detector: _ChainDetector, fix_hint: str
) -> list[Match]:
    lineno, raw, masked = line
    detector, pattern, is_dom = chain_detector
    return [
        _make_match(
            detector,
            lineno,
            m.start(),
            raw,
            fix_hint,
            {"receiver": m.group("receiver") or "", "op": m.group("op") or ""},
        )
        for m in pattern.finditer(masked)
        if not is_dom(m.group("receiver") or "")
    ]


def detect_compound_assignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return [
        match
        for line in _iter_lines(text)
        for chain_detector in _COMPOUND_DETECTORS
        for match in _chain_hits(line, chain_detector, _COMPOUND_FIX)
    ]


def detect_increment_decrement(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return [
        match
        for line in _iter_lines(text)
        for chain_detector in _INCREMENT_DETECTORS
        for match in _chain_hits(line, chain_detector, _INCREMENT_FIX)
    ]


def detect_optional_chain_assignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return [
        _make_match(
            "experimental.optional-chain-assignment",
            lineno,
            m.start(),
            raw,
            _OPTIONAL_CHAIN_FIX,
            {"receiver": m.group("receiver") or "", "prop": m.group("prop") or ""},
        )
        for lineno, raw, masked in _undeclared_lines(text)
        for m in OPTIONAL_CHAIN_ASSIGN_PATTERN.finditer(masked)
    ]


def detect_private_field_assignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return [
        _make_match(
            detector,
            lineno,
            m.start(),
            raw,
            _PRIVATE_FIELD_FIX,
            {
                "receiver": m.group("receiver") or "",
                "field": m.group("field") or "",
                "op": m.group("op") or default_op,
            },
        )
        for lineno, raw, masked in _undeclared_lines(text)
        for detector, pattern, default_op in _PRIVATE_FIELD_DETECTORS
        for m in pattern.finditer(masked)
        if not _is_comparison(m.group(0))
    ]


def detect_symbol_key_assignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return [
        _make_match(
            "symbol-key.assignment",
            lineno,
            m.start(),
            raw,
            _SYMBOL_KEY_FIX,
            {
                "receiver": m.group("receiver") or "",
                "key": (m.group("key") or "").strip(),
            },
        )
        for lineno, raw, masked in _undeclared_lines(text)
        for m in SYMBOL_KEY_ASSIGN_PATTERN.finditer(masked)
        if not _is_comparison(m.group(0))
        and not is_dom_receiver(m.group("receiver") or "")
    ]
