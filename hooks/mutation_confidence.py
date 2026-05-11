#!/usr/bin/env python3
"""Confidence scoring for mutation-method-blocker findings.

Plan items 265-267 (D40). A finding's confidence is the model's belief
that the match is genuine (not a false positive). Score range is 1-10:

  - 10  Receiver type is known and AST confirmed; canonical mutating call.
  -  7  AST confirmed; receiver type is plausible (typed-suffix heuristic).
  -  5  AST not run, regex-only match against an unambiguous pattern.
  -  3  AST not run; receiver shape is ambiguous (e.g., chained access).
  -  1  Disabled detector or low-signal heuristic.

Wired into:
  - Audit log: `confidence_score` field per block decision.
  - SARIF: maps to `level` (error >= 5, warning 3-4, note <= 2).

The scoring is deliberately coarse. Treat the number as a hint, not a
precise probability.
"""

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

# Receiver suffixes that strongly suggest a typed array or DOM-adjacent value
# even without explicit type annotation in the surrounding code.
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
    """Return a confidence score in [1, 10].

    Args:
        detector: tag like `array.push`, `collection.map.set`.
        ast_confirmed: True when ast-grep validated the call site.
        receiver_known: True when the receiver name has a typed suffix
            or an explicit type annotation.
        file_path: path of the file being analyzed (used for hot-path
            sensitivity adjustments in future versions).
    """
    canonical = _is_canonical(detector)
    if not canonical:
        # Heuristic detectors top out at REGEX_CANONICAL; AST nudges them up.
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
    """Map a confidence score to a SARIF severity level."""
    if score >= 5:
        return "error"
    if score >= 3:
        return "warning"
    return "note"


def clamp(score: int) -> int:
    """Clamp a score to the documented [1, 10] range."""
    if score < 1:
        return 1
    if score > 10:
        return 10
    return score
