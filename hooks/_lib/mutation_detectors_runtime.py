from __future__ import annotations

import re

from .mutation_allowlists import has_temporal_usage
from .mutation_detectors_core import Match, mask_text
from .mutation_scan_helpers import ScannedLine, iter_stripped_lines, make_match

DATE_SETTERS: tuple[str, ...] = (
    "setDate",
    "setFullYear",
    "setHours",
    "setMilliseconds",
    "setMinutes",
    "setMonth",
    "setSeconds",
    "setTime",
    "setYear",
    "setUTCDate",
    "setUTCFullYear",
    "setUTCHours",
    "setUTCMilliseconds",
    "setUTCMinutes",
    "setUTCMonth",
    "setUTCSeconds",
)

DATE_SETTER_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.(?P<method>" + "|".join(DATE_SETTERS) + r")\s*\("
)

DATE_RECEIVER_HINT = re.compile(
    r"\b(?:[a-zA-Z_$][\w$]*(?:Date|date|Time|time|Timestamp|timestamp|Stamp|stamp|Day|day|Moment|moment|Now|now))\b|new\s+Date\s*\("
)

DATE_CONSTRUCTOR_CHAIN_PATTERN = re.compile(
    r"new\s+Date\s*\(\s*[a-zA-Z_$][\w$]*\s*\.(?:" + "|".join(DATE_SETTERS) + r")\s*\("
)

PROXY_HANDLER_TRAP_PATTERN = re.compile(
    r"\b(?P<trap>set|deleteProperty|defineProperty|setPrototypeOf)\s*\("
)

PROXY_HANDLER_CONTEXT_PATTERN = re.compile(
    r"new\s+Proxy\s*\(|Proxy\.revocable\s*\(|handler\s*[:=]"
)

WEAKREF_DEREF_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.deref\s*\(\s*\)\s*[?]?\.(?P<method>[a-zA-Z_$][\w$]*)\s*\("
)

WEAKREF_DECL_PATTERN = re.compile(r"new\s+WeakRef\s*\(")

FINALIZATION_REGISTRY_PATTERN = re.compile(r"new\s+FinalizationRegistry\s*\(")

FOR_AWAIT_HEADER_PATTERN = re.compile(
    r"\bfor\s+await\s*\(\s*(?:const|let|var)\s+(?P<binding>[a-zA-Z_$][\w$]*)"
)

PUSH_INSIDE_BODY_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.push\s*\(")

OBJECT_GROUPBY_PATTERN = re.compile(r"\bObject\s*\.\s*groupBy\s*\(")
GROUPBY_BUCKET_PUSH_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\[\s*[^\]]+\]\s*\.push\s*\("
)

_WEAKREF_MUTATING_METHODS: frozenset[str] = frozenset(
    {
        "push",
        "pop",
        "shift",
        "unshift",
        "splice",
        "sort",
        "reverse",
        "fill",
        "copyWithin",
        "set",
        "delete",
        "clear",
        "add",
    }
)

_DATE_TEMPORAL_FIXES = (
    "Date setters mutate the receiver. The file already uses Temporal; prefer "
    "`Temporal.PlainDate.from(d).with({ month: m })`, `instant.add({ hours: 1 })`, or "
    "`zoned.subtract({ days: 7 })`. Temporal returns are immutable. Rule: "
    "~/.claude/rules/code-style.md Date and Time Handling.",
    "`new Date(d.setMonth(...))` mutates `d` AND uses the mutated value as a constructor "
    "argument; the resulting Date and the original now share state. The file uses Temporal; "
    "prefer `Temporal.PlainDate.from(d.toISOString()).with({ month: m })` or convert the "
    "Date upstream and stay in Temporal.",
)
_DATE_FNS_FIXES = (
    "Date setters mutate the receiver. Use date-fns immutable helpers: `subMonths(d, 1)`, "
    "`addDays(d, 7)`, `setHours` from date-fns returns a new Date. The Temporal API "
    "(Stage 4 / ES2026) is the long-term replacement; consider adopting "
    "`@js-temporal/polyfill` for new code. Rule: "
    "~/.claude/rules/code-style.md Date and Time Handling.",
    "`new Date(d.setMonth(...))` mutates `d` AND uses the mutated value as a constructor "
    "argument; the resulting Date and the original now share state. Use `addMonths(d, n)` "
    "or `setMonth(d, m)` from date-fns instead. Temporal API is Stage 4 / ES2026.",
)
_PROXY_TRAP_FIX = (
    "Mutating Proxy traps (`set`, `deleteProperty`, `defineProperty`, `setPrototypeOf`) "
    "expose mutation to consumers. Prefer a copy-on-write strategy: the trap returns a "
    "new proxy wrapping the modified data, and the original stays untouched. When the "
    "Proxy is genuinely a mutable façade, document that contract in the handler's JSDoc "
    "and keep the facade behind one module boundary."
)
_WEAKREF_FIX = (
    "Mutating through `weakRef.deref()` is unsafe: the GC can collect the target between "
    "your deref and the call. If the operation must succeed, hold a strong reference for "
    "the duration. If the operation is best-effort, check `const target = weakRef.deref(); "
    "if (target) { ... }` and treat absence as a no-op. Beyond safety, prefer non-mutating "
    "operations on the dereferenced value."
)
_FINALIZATION_FIX = (
    "FinalizationRegistry callbacks run at unpredictable GC moments. Keep the callback "
    "side-effect-minimal: log, close a file handle, or release a connection. Never mutate "
    "shared application state from the callback. Spec note: callbacks may not run at all "
    "if the registry itself is collected. Treat the callback as best-effort cleanup."
)
_FOR_AWAIT_PUSH_FIX = (
    "Replace `for await (const x of asyncIter) { result.push(x) }` with "
    "`const result = await Array.fromAsync(asyncIter)` (ES2024). For a transformation, "
    "use `Array.fromAsync(asyncIter, x => transform(x))` which accepts a mapper. Once "
    "the runtime targets ES2025+, switch to AsyncIterator helpers: `asyncIter.map(fn).toArray()`."
)
_GROUPBY_PUSH_FIX = (
    "`Object.groupBy(items, key)` returns a record whose buckets are "
    "arrays. Pushing into a bucket mutates that array and breaks the "
    "immutable contract of the helper. Use `Map.groupBy` plus a reducer "
    "that produces fresh arrays, or compute the buckets with "
    "`items.reduce((acc, x) => ({ ...acc, [k(x)]: [...(acc[k(x)] ?? []), x] }), {})`."
)


def _date_line_matches(
    line: ScannedLine, fixes: tuple[str, str], use_temporal: bool
) -> list[Match]:
    lineno, raw, masked = line
    setter_fix, chain_fix = fixes
    chains = [
        make_match("date.constructor-chain", lineno, m.start(), raw, chain_fix)
        for m in DATE_CONSTRUCTOR_CHAIN_PATTERN.finditer(masked)
    ]
    setters = [
        make_match(
            f"date.{m.group('method')}",
            lineno,
            m.start(),
            raw,
            setter_fix,
            {
                "owner": m.group("owner") or "",
                "method": m.group("method") or "",
                "temporal_in_scope": "1" if use_temporal else "0",
            },
        )
        for m in DATE_SETTER_PATTERN.finditer(masked)
    ]
    return [*chains, *setters]


def detect_date_setters(text: str, lang: str | None, file_path: str) -> list[Match]:
    if not DATE_RECEIVER_HINT.search(text):
        return []
    use_temporal = has_temporal_usage(text)
    fixes = _DATE_TEMPORAL_FIXES if use_temporal else _DATE_FNS_FIXES
    return [
        match
        for line in iter_stripped_lines(text)
        for match in _date_line_matches(line, fixes, use_temporal)
    ]


def _proxy_handler_lines(text: str) -> list[ScannedLine]:
    selected: list[ScannedLine] = []
    in_handler = False
    brace_depth = 0
    for lineno, raw, line_masked in iter_stripped_lines(text):
        if PROXY_HANDLER_CONTEXT_PATTERN.search(line_masked):
            in_handler = True
            brace_depth = 0
        if not in_handler:
            continue
        brace_depth += line_masked.count("{") - line_masked.count("}")
        selected.append((lineno, raw, line_masked))
        if brace_depth <= 0 and "}" in line_masked:
            in_handler = False
    return selected


def detect_proxy_mutating_traps(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    if not PROXY_HANDLER_CONTEXT_PATTERN.search(mask_text(text)):
        return []
    return [
        make_match(
            "proxy.trap." + m.group("trap"),
            lineno,
            m.start(),
            raw,
            _PROXY_TRAP_FIX,
            {"trap": m.group("trap"), "confidence": "4"},
        )
        for lineno, raw, line_masked in _proxy_handler_lines(text)
        for m in PROXY_HANDLER_TRAP_PATTERN.finditer(line_masked)
    ]


def _mentions_weakref(masked: str) -> bool:
    return bool(
        WEAKREF_DECL_PATTERN.search(masked) or "WeakRef" in masked or ".deref" in masked
    )


def detect_weakref_then_mutate(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    if not _mentions_weakref(mask_text(text)):
        return []
    return [
        make_match(
            "weakref.deref-mutate." + m.group("method"),
            lineno,
            m.start(),
            raw,
            _WEAKREF_FIX,
            {
                "owner": m.group("owner") or "",
                "method": m.group("method"),
                "confidence": "5",
            },
        )
        for lineno, raw, line_masked in iter_stripped_lines(text)
        for m in WEAKREF_DEREF_PATTERN.finditer(line_masked)
        if m.group("method") in _WEAKREF_MUTATING_METHODS
    ]


def detect_finalization_registry(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    if not FINALIZATION_REGISTRY_PATTERN.search(mask_text(text)):
        return []
    return [
        make_match(
            "finalization-registry.construct",
            lineno,
            m.start(),
            raw,
            _FINALIZATION_FIX,
            {"confidence": "1", "severity": "info"},
        )
        for lineno, raw, line_masked in iter_stripped_lines(text)
        for m in FINALIZATION_REGISTRY_PATTERN.finditer(line_masked)
    ]


def _brace_delta(line_masked: str) -> int:
    return line_masked.count("{") - line_masked.count("}")


def _for_await_body_lines(iter_lines: list[ScannedLine]) -> list[ScannedLine]:
    selected: list[ScannedLine] = []
    in_for_await = False
    brace_depth = 0
    for line in iter_lines:
        line_masked = line[2]
        if FOR_AWAIT_HEADER_PATTERN.search(line_masked):
            in_for_await = True
            brace_depth = _brace_delta(line_masked)
            continue
        if not in_for_await:
            continue
        brace_depth += _brace_delta(line_masked)
        selected.append(line)
        if brace_depth <= 0:
            in_for_await = False
    return selected


def detect_for_await_push_pattern(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    iter_lines = iter_stripped_lines(text)
    if not any(FOR_AWAIT_HEADER_PATTERN.search(masked) for _, _, masked in iter_lines):
        return []
    if not any(".push(" in masked for _, _, masked in iter_lines):
        return []
    return [
        make_match(
            "async-iterable.for-await-push",
            lineno,
            m.start(),
            raw,
            _FOR_AWAIT_PUSH_FIX,
            {"owner": m.group("owner") or "", "confidence": "6"},
        )
        for lineno, raw, line_masked in _for_await_body_lines(iter_lines)
        for m in PUSH_INSIDE_BODY_PATTERN.finditer(line_masked)
    ]


def detect_object_groupby_push(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    iter_lines = iter_stripped_lines(text)
    if not OBJECT_GROUPBY_PATTERN.search(text):
        return []
    if not any(
        GROUPBY_BUCKET_PUSH_PATTERN.search(masked) for _, _, masked in iter_lines
    ):
        return []
    return [
        make_match(
            "object.group-by-bucket-push",
            lineno,
            m.start(),
            raw,
            _GROUPBY_PUSH_FIX,
            {"owner": m.group("owner") or "", "confidence": "3"},
        )
        for lineno, raw, line_masked in iter_lines
        for m in GROUPBY_BUCKET_PUSH_PATTERN.finditer(line_masked)
    ]
