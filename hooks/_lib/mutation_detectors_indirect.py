from __future__ import annotations

import re

from .mutation_detectors_core import Match
from .mutation_scan_helpers import iter_masked_lines, make_match

MUTATOR_NAMES = (
    "push|pop|shift|unshift|splice|sort|reverse|fill|copyWithin|set|add|delete|clear"
)

INDIRECT_MUTATOR_PATTERN = re.compile(
    r"(?P<receiver>\[\s*\]|\b(?:Array|Map|Set|WeakMap|WeakSet)\.prototype|[A-Za-z_$][\w$]*)"
    rf"\s*\.\s*(?P<method>{MUTATOR_NAMES})\s*\.\s*(?:call|apply|bind)\s*\("
)

MEMBER = r"[A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*|\s*\[[^\]]+\])+"

ARRAY_PATTERN_OPEN = re.compile(r"^\s*;?\s*\[")
MEMBER_PATTERN = re.compile(MEMBER)
ASSIGNMENT_AFTER = re.compile(r"\s*=(?![=>])")

OBJECT_DESTRUCTURE_TARGET = re.compile(
    rf"^\s*;?\s*\(\s*\{{(?P<targets>[^}}]*:\s*{MEMBER}[^}}]*)\}}\s*=(?![=>])"
)

FOR_MEMBER_TARGET = re.compile(
    rf"\bfor\s*(?:await\s*)?\(\s*(?!(?:const|let|var)\b)(?P<target>{MEMBER})\s+(?:of|in)\b"
)

_INDIRECT_FIX = (
    "Calling a mutator through `.call`, `.apply` or `.bind` still mutates the receiver. "
    "Build a new value instead: `[...arr, item]`, `arr.toSorted()`, `new Map([...map, [k, v]])`."
)
_DESTRUCTURE_FIX = (
    "Destructuring into existing properties writes to them. Destructure into new "
    "`const` bindings and build the result object: `const { a, b } = src; return { ...obj, a, b }`."
)
_FOR_TARGET_FIX = (
    "A `for...of` or `for...in` loop with a property as its target writes that property on "
    "every iteration. Declare a loop binding with `const` and derive the value."
)


def detect_indirect_mutator_call(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return [
        make_match(
            "array.mutator-indirect",
            lineno,
            m.start(),
            raw,
            _INDIRECT_FIX,
            {"receiver": m.group("receiver"), "method": m.group("method")},
        )
        for lineno, raw, masked in iter_masked_lines(text)
        for m in INDIRECT_MUTATOR_PATTERN.finditer(masked)
    ]


def _closing_bracket(masked: str, start: int) -> int:
    depth = 0
    for index in range(start, len(masked)):
        depth += {"[": 1, "]": -1}.get(masked[index], 0)
        if depth == 0:
            return index
    return -1


def _is_array_member_pattern(masked: str) -> bool:
    opened = ARRAY_PATTERN_OPEN.match(masked)
    if opened is None:
        return False
    close = _closing_bracket(masked, opened.end() - 1)
    if close < 0 or ASSIGNMENT_AFTER.match(masked, close + 1) is None:
        return False
    return MEMBER_PATTERN.search(masked, opened.end(), close) is not None


def _is_destructuring_member_target(masked: str) -> bool:
    if OBJECT_DESTRUCTURE_TARGET.match(masked) is not None:
        return True
    return _is_array_member_pattern(masked)


def detect_destructuring_member_target(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return [
        make_match("property.destructure-target", lineno, 0, raw, _DESTRUCTURE_FIX)
        for lineno, raw, masked in iter_masked_lines(text)
        if _is_destructuring_member_target(masked)
    ]


def detect_for_member_target(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return [
        make_match(
            "property.for-target",
            lineno,
            m.start("target"),
            raw,
            _FOR_TARGET_FIX,
            {"target": m.group("target")},
        )
        for lineno, raw, masked in iter_masked_lines(text)
        for m in FOR_MEMBER_TARGET.finditer(masked)
    ]
