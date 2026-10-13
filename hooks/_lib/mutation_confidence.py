#!/usr/bin/env python3
from __future__ import annotations

CONFIDENCE_HIGH = 10
CONFIDENCE_AST_TYPED = 9
CONFIDENCE_AST_PLAUSIBLE = 7
CONFIDENCE_REGEX_CANONICAL = 5
CONFIDENCE_REGEX_AMBIGUOUS = 3
CONFIDENCE_LOW = 1

CANONICAL_DETECTORS: frozenset[str] = frozenset(
    {
        "array.push",
        "array.pop",
        "array.shift",
        "array.unshift",
        "array.splice",
        "array.sort",
        "array.reverse",
        "array.fill",
        "array.copyWithin",
        "collection.map.set",
        "collection.map.delete",
        "collection.map.clear",
        "collection.set.add",
        "collection.set.delete",
        "collection.set.clear",
        "typed-array.set",
        "typed-array.fill",
        "typed-array.sort",
        "typed-array.reverse",
        "typed-array.copyWithin",
    }
)

TYPED_SUFFIX_HINTS: tuple[str, ...] = (
    "Array",
    "List",
    "Items",
    "Buffer",
    "Queue",
    "Stack",
    "Map",
    "Set",
)


def _is_canonical(detector: str) -> bool:
    return detector in CANONICAL_DETECTORS


def _has_typed_suffix(receiver: str) -> bool:
    return any(receiver.endswith(s) for s in TYPED_SUFFIX_HINTS)


def score_finding(
    detector: str,
    *,
    ast_confirmed: bool,
    receiver_known: bool,
    file_path: str,
) -> int:
    canonical = _is_canonical(detector)
    if not canonical:
        if ast_confirmed and receiver_known:
            return CONFIDENCE_AST_PLAUSIBLE
        if ast_confirmed:
            return CONFIDENCE_REGEX_CANONICAL
        return CONFIDENCE_REGEX_AMBIGUOUS

    if ast_confirmed and receiver_known:
        return CONFIDENCE_HIGH
    if ast_confirmed:
        return CONFIDENCE_AST_TYPED
    if receiver_known:
        return CONFIDENCE_AST_PLAUSIBLE
    return CONFIDENCE_REGEX_CANONICAL


def to_sarif_level(score: int) -> str:
    if score >= 5:
        return "error"
    if score >= 3:
        return "warning"
    return "note"


def clamp(score: int) -> int:
    if score < 1:
        return 1
    if score > 10:
        return 10
    return score
