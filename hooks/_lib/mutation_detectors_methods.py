from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .mutation_allowlists import (
    collect_temporal_receivers,
    collect_web_api_receivers,
    has_temporal_usage,
    is_temporal_chain_call,
    is_web_api_receiver,
)
from .mutation_detectors_core import Match
from .mutation_scan_helpers import iter_stripped_lines as _iter_lines
from .mutation_scan_helpers import make_match as _make_match

PUSH_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.push\s*\(")
POP_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.pop\s*\(")
SHIFT_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.shift\s*\(")
UNSHIFT_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.unshift\s*\(")
SPLICE_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.splice\s*\(")
SORT_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.sort\s*\(")
REVERSE_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.reverse\s*\(")
FILL_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.fill\s*\(")
COPYWITHIN_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.copyWithin\s*\(")

BRACKET_DISPATCH_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\[\s*['\"](?P<method>push|pop|shift|unshift|splice|sort|reverse|fill|copyWithin)['\"]\s*\]\s*\("
)

MAP_SET_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.set\s*\(")
MAP_DELETE_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.delete\s*\(")
MAP_CLEAR_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.clear\s*\(")
SET_ADD_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.add\s*\(")

MAP_RECEIVER_HINT = re.compile(
    r"(?<![.\w$])(?:Map|Maps|map)\b(?!\s*\()|new\s+Map\s*\(|:\s*Map[<\s,]"
)
SET_RECEIVER_HINT = re.compile(
    r"(?<![.\w$])(?:Set|Sets|set)\b(?!\s*\()|new\s+Set\s*\(|:\s*Set[<\s,]"
)
COLLECTION_DECLARATION = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*"
    r"(?::\s*(?:Readonly)?(?P<annotated>WeakMap|WeakSet|Map|Set)\b[^=;\n]*)?"
    r"(?:=\s*new\s+(?P<constructed>WeakMap|WeakSet|Map|Set)\b)?"
)
WEAKMAP_RECEIVER_HINT = re.compile(r"\bWeakMap\b|new\s+WeakMap\s*\(")
WEAKSET_RECEIVER_HINT = re.compile(r"\bWeakSet\b|new\s+WeakSet\s*\(")

MAP_UPSERT_METHODS: tuple[str, ...] = ("getOrInsert", "getOrInsertComputed")

MAP_UPSERT_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.(?P<method>"
    + "|".join(MAP_UPSERT_METHODS)
    + r")\s*\("
)

_COLLECTION_WINDOW_BEFORE = 5
_COLLECTION_WINDOW_AFTER = 4

_ARRAY_DETECTORS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "array.pop",
        POP_PATTERN,
        "Replace `arr.pop()` with `arr.slice(0, -1)`. Use `arr.at(-1)` to read the last value without removing it.",
    ),
    (
        "array.shift",
        SHIFT_PATTERN,
        "Replace `arr.shift()` with `arr.slice(1)`. Use `arr.at(0)` to read the first value without removing it.",
    ),
    (
        "array.unshift",
        UNSHIFT_PATTERN,
        "Replace `arr.unshift(item)` with `[item, ...arr]`.",
    ),
    (
        "array.splice",
        SPLICE_PATTERN,
        "Replace `arr.splice(start, count, ...items)` with `arr.toSpliced(start, count, ...items)` (ES2023) or `[...arr.slice(0, start), ...items, ...arr.slice(start + count)]`.",
    ),
    (
        "array.reverse",
        REVERSE_PATTERN,
        "Replace `arr.reverse()` with `arr.toReversed()` (ES2023) or `[...arr].reverse()`.",
    ),
    (
        "array.fill",
        FILL_PATTERN,
        "Replace `arr.fill(v)` with `Array.from({length: arr.length}, () => v)` or `arr.map(() => v)`.",
    ),
    (
        "array.copyWithin",
        COPYWITHIN_PATTERN,
        "Replace `arr.copyWithin(...)` with an explicit `arr.map((v, i) => ...)` that produces the desired index mapping.",
    ),
)

_ARRAY_PUSH_FIX = (
    "Replace `arr.push(item)` with `arr = [...arr, item]` or include the new item directly: "
    "`return [...arr, item]`. For typed parameters, mark them `readonly T[]` to surface "
    "this at compile time. Framework navigation (router.push, history.push) is auto-allowed."
)
_ARRAY_SORT_FIX = (
    "Replace `arr.sort(fn)` with `arr.toSorted(fn)` (ES2023) or `[...arr].sort(fn)`. "
    "For typed parameters, mark them `readonly T[]` to surface this at compile time."
)
_BRACKET_DISPATCH_FIX = (
    "Bracket-string dispatch (`arr['push'](x)`) bypasses static analysis and the spread-based "
    "alternative. Use the immutable equivalent for the underlying method (toSorted, toReversed, "
    "toSpliced, with). The dispatch pattern itself is a code smell separate from the mutation."
)
_MAP_UPSERT_FIX = (
    "Stage 4 `Map.prototype.getOrInsert(key, default)` and "
    "`getOrInsertComputed(key, factory)` mutate the receiver when the key "
    "is missing. For immutable callers use "
    "`map.has(k) ? map.get(k) : default` over a fresh "
    "`new Map([...map, [k, default]])`. Suppress with "
    "a local cache for "
    "memoization receivers."
)

_GUARD_TEMPORAL_AND_WEB_API = (True, True)
_GUARD_WEB_API_ONLY = (False, True)
_GUARD_NONE = (False, False)


def detect_array_pop_shift_unshift_splice_reverse_fill_copywithin(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    web_api_receivers = collect_web_api_receivers(text)
    return [
        _make_match(
            detector,
            lineno,
            m.start(),
            raw,
            fix_hint,
            {"owner": m.group("owner") or ""},
        )
        for lineno, raw, masked in _iter_lines(text)
        for detector, pattern, fix_hint in _ARRAY_DETECTORS
        for m in pattern.finditer(masked)
        if not is_web_api_receiver(m.group("owner") or "", web_api_receivers)
    ]


def detect_array_push(text: str, lang: str | None, file_path: str) -> list[Match]:
    web_api_receivers = collect_web_api_receivers(text)
    return [
        _make_match(
            "array.push",
            lineno,
            m.start(),
            raw,
            _ARRAY_PUSH_FIX,
            {"owner": m.group("owner") or "", "raw_line": raw},
        )
        for lineno, raw, masked in _iter_lines(text)
        for m in PUSH_PATTERN.finditer(masked)
        if not is_web_api_receiver(m.group("owner") or "", web_api_receivers)
    ]


def detect_array_sort(text: str, lang: str | None, file_path: str) -> list[Match]:
    web_api_receivers = collect_web_api_receivers(text)
    return [
        _make_match(
            "array.sort",
            lineno,
            m.start(),
            raw,
            _ARRAY_SORT_FIX,
            {"owner": m.group("owner") or ""},
        )
        for lineno, raw, masked in _iter_lines(text)
        for m in SORT_PATTERN.finditer(masked)
        if not is_web_api_receiver(m.group("owner") or "", web_api_receivers)
    ]


def _is_masked_owner(masked: str, owner_start: int) -> bool:
    return owner_start < len(masked) and masked[owner_start] == " "


def detect_bracket_dispatch(text: str, lang: str | None, file_path: str) -> list[Match]:
    return [
        _make_match(
            f"array.bracket-dispatch.{m.group('method')}",
            lineno,
            m.start(),
            raw,
            _BRACKET_DISPATCH_FIX,
            {"owner": m.group("owner") or "", "method": m.group("method") or ""},
        )
        for lineno, raw, masked in _iter_lines(text)
        for m in BRACKET_DISPATCH_PATTERN.finditer(raw)
        if not _is_masked_owner(masked, m.start())
    ]


def _collection_receiver_kind(window: str) -> str | None:
    kinds = _collection_receiver_kinds(window)
    return kinds[0] if kinds else None


def _collection_receiver_kinds(window: str) -> tuple[str, ...]:
    hints = (
        ("WeakMap", WEAKMAP_RECEIVER_HINT),
        ("WeakSet", WEAKSET_RECEIVER_HINT),
        ("Map", MAP_RECEIVER_HINT),
        ("Set", SET_RECEIVER_HINT),
    )
    return tuple(kind for kind, hint in hints if hint.search(window))


def _declared_collection_kinds(text: str) -> dict[str, str]:
    return {
        m.group("owner"): m.group("constructed") or m.group("annotated")
        for m in COLLECTION_DECLARATION.finditer(text)
        if m.group("constructed") or m.group("annotated")
    }


def _owner_filter(
    kind: str, primary: str, declared: dict[str, str]
) -> Callable[[str | None], bool]:
    def accepts(owner: str | None) -> bool:
        return declared.get(owner or "", primary) == kind

    return accepts


@dataclass(frozen=True)
class _CollectionLine:
    lineno: int
    raw: str
    masked: str
    kind: str
    temporal_receivers: frozenset[str]
    web_api_receivers: frozenset[str]
    accepts: Callable[[str | None], bool]


def _owner_is_flagged(
    line: _CollectionLine, owner: str | None, guards: tuple[bool, bool]
) -> bool:
    guard_temporal, guard_web_api = guards
    if not line.accepts(owner):
        return False
    if guard_temporal and is_temporal_chain_call(
        line.raw, owner, line.temporal_receivers
    ):
        return False
    return not (guard_web_api and is_web_api_receiver(owner, line.web_api_receivers))


def _collection_hits(
    line: _CollectionLine,
    operation: tuple[str, re.Pattern[str], str],
    guards: tuple[bool, bool],
) -> list[Match]:
    name, pattern, fix_hint = operation
    return [
        _make_match(
            f"collection.{line.kind.lower()}.{name}",
            line.lineno,
            m.start(),
            line.raw,
            fix_hint,
            {"kind": line.kind},
        )
        for m in pattern.finditer(line.masked)
        if _owner_is_flagged(line, m.group("owner"), guards)
    ]


def _map_fixes(kind: str) -> tuple[str, str, str]:
    if kind == "Map":
        return (
            f"Replace `{kind.lower()}.set(k, v)` with `new {kind}([...{kind.lower()}, [k, v]])`. "
            f"Mark the parameter `Readonly{kind}<K, V>` to enforce immutability at the type level.",
            f"Replace `{kind.lower()}.delete(k)` with `new {kind}([...{kind.lower()}].filter(([key]) => key !== k))`.",
            f"Replace `{kind.lower()}.clear()` with `new {kind}()` and reassign.",
        )
    return (
        "WeakMap mutation: WeakMaps cannot be iterated, so a new instance loses every existing entry. Confirm the lifetime is genuinely a fresh-instance flow before suppressing.",
        "WeakMap deletion is rare and may be intended. Document the lifetime at the call site by naming the owning scope.",
        "WeakMaps cannot be cleared; the call is a no-op or a code smell. Investigate the intent.",
    )


def _set_fixes(kind: str) -> tuple[str, str, str]:
    if kind == "Set":
        return (
            f"Replace `{kind.lower()}.add(v)` with `new {kind}([...{kind.lower()}, v])`. "
            f"For lookups that must not grow, type the parameter as `Readonly{kind}<T>`.",
            f"Replace `{kind.lower()}.delete(v)` with `new {kind}([...{kind.lower()}].filter(x => x !== v))`.",
            f"Replace `{kind.lower()}.clear()` with `new {kind}()` and reassign.",
        )
    return (
        "WeakSet mutation: WeakSets cannot be iterated, so a fresh instance loses every entry. Document the lifetime explicitly.",
        "WeakSet deletion is rare. When the intent is correct, keep the deletion inside the scope that owns the set.",
        "WeakSets cannot be cleared; the call is a no-op.",
    )


def _emit_map_mutations(line: _CollectionLine) -> list[Match]:
    set_fix, delete_fix, clear_fix = _map_fixes(line.kind)
    clears = (
        _collection_hits(
            line, ("clear", MAP_CLEAR_PATTERN, clear_fix), _GUARD_WEB_API_ONLY
        )
        if line.kind == "Map"
        else []
    )
    return [
        *_collection_hits(
            line, ("set", MAP_SET_PATTERN, set_fix), _GUARD_TEMPORAL_AND_WEB_API
        ),
        *_collection_hits(
            line,
            ("delete", MAP_DELETE_PATTERN, delete_fix),
            _GUARD_TEMPORAL_AND_WEB_API,
        ),
        *clears,
    ]


def _emit_set_mutations(line: _CollectionLine) -> list[Match]:
    add_fix, delete_fix, clear_fix = _set_fixes(line.kind)
    clears = (
        _collection_hits(line, ("clear", MAP_CLEAR_PATTERN, clear_fix), _GUARD_NONE)
        if line.kind == "Set"
        else []
    )
    return [
        *_collection_hits(
            line, ("add", SET_ADD_PATTERN, add_fix), _GUARD_TEMPORAL_AND_WEB_API
        ),
        *_collection_hits(
            line,
            ("delete", MAP_DELETE_PATTERN, delete_fix),
            _GUARD_TEMPORAL_AND_WEB_API,
        ),
        *clears,
    ]


def _emit_collection_mutations(line: _CollectionLine) -> list[Match]:
    if line.kind.endswith("Map"):
        return _emit_map_mutations(line)
    return _emit_set_mutations(line)


def _collection_window(lines: list[str], lineno: int) -> str:
    start = max(0, lineno - _COLLECTION_WINDOW_BEFORE)
    return "\n".join(lines[start : lineno + _COLLECTION_WINDOW_AFTER])


@dataclass(frozen=True)
class _CollectionContext:
    lines: list[str]
    temporal_receivers: frozenset[str]
    web_api_receivers: frozenset[str]
    declared: dict[str, str]


def _collection_line_matches(
    context: _CollectionContext, lineno: int, raw: str, masked: str
) -> list[Match]:
    kinds = _collection_receiver_kinds(_collection_window(context.lines, lineno))
    return [
        match
        for kind in kinds
        for match in _emit_collection_mutations(
            _CollectionLine(
                lineno=lineno,
                raw=raw,
                masked=masked,
                kind=kind,
                temporal_receivers=context.temporal_receivers,
                web_api_receivers=context.web_api_receivers,
                accepts=_owner_filter(kind, kinds[0], context.declared),
            )
        )
    ]


def detect_map_set_collection_mutations(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    context = _CollectionContext(
        lines=text.splitlines(),
        temporal_receivers=(
            collect_temporal_receivers(text)
            if has_temporal_usage(text)
            else frozenset()
        ),
        web_api_receivers=collect_web_api_receivers(text),
        declared=_declared_collection_kinds(text),
    )
    return [
        match
        for lineno, raw, masked in _iter_lines(text)
        for match in _collection_line_matches(context, lineno, raw, masked)
    ]


def detect_map_upsert(text: str, lang: str | None, file_path: str) -> list[Match]:
    iter_lines = _iter_lines(text)
    if not any(MAP_UPSERT_PATTERN.search(masked) for _, _, masked in iter_lines):
        return []
    if not MAP_RECEIVER_HINT.search(text):
        return []
    return [
        _make_match(
            "collection.map.get-or-insert"
            if m.group("method") == "getOrInsert"
            else "collection.map.get-or-insert-computed",
            lineno,
            m.start(),
            raw,
            _MAP_UPSERT_FIX,
            {
                "owner": m.group("owner") or "",
                "method": m.group("method"),
                "confidence": "4",
            },
        )
        for lineno, raw, line_masked in iter_lines
        for m in MAP_UPSERT_PATTERN.finditer(line_masked)
    ]
