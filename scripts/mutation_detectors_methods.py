"""Method-call mutation detectors.

Covers in-place mutations expressed as method calls on a receiver:

  - Array prototype: push, pop, shift, unshift, splice, sort, reverse,
    fill, copyWithin.
  - Map and Set prototypes: set, delete, clear, add.
  - WeakMap and WeakSet: set, delete, add.
  - TypedArray prototypes: set, fill, sort, reverse, copyWithin (with
    hot-path skip for crypto, codec, image, and similar domains).
  - Date prototype setters: 15 mutating methods covering year, month,
    date, hours, minutes, seconds, milliseconds, plus their UTC variants.

Each detector is a pure function over a text payload. It returns a list
of `Match` objects with line, column, detector tag, and a fix hint that
references the ES2023 non-mutating equivalent or the relevant rule.
"""

from __future__ import annotations

import re

from mutation_allowlists import (
    collect_temporal_receivers,
    collect_web_api_receivers,
    has_temporal_usage,
    is_temporal_chain_call,
    is_web_api_receiver,
)
from mutation_detectors_core import (
    Match,
    strip_strings_comments,
    truncate_excerpt,
)

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

MAP_RECEIVER_HINT = re.compile(r"\b(?:Map|Maps|map)\b|new\s+Map\s*\(|:\s*Map[<\s,]")
SET_RECEIVER_HINT = re.compile(r"\b(?:Set|Sets|set)\b|new\s+Set\s*\(|:\s*Set[<\s,]")
WEAKMAP_RECEIVER_HINT = re.compile(r"\bWeakMap\b|new\s+WeakMap\s*\(")
WEAKSET_RECEIVER_HINT = re.compile(r"\bWeakSet\b|new\s+WeakSet\s*\(")

TYPED_ARRAY_TYPES: tuple[str, ...] = (
    "Int8Array",
    "Uint8Array",
    "Uint8ClampedArray",
    "Int16Array",
    "Uint16Array",
    "Int32Array",
    "Uint32Array",
    "Float16Array",
    "Float32Array",
    "Float64Array",
    "BigInt64Array",
    "BigUint64Array",
)

TYPED_ARRAY_DECL_PATTERN = re.compile(
    r"new\s+(?:" + "|".join(TYPED_ARRAY_TYPES) + r")\s*\("
)

TYPED_ARRAY_NAME_HINT_PATTERN = re.compile(
    r"\b(?:[a-zA-Z_$][\w$]*(?:Buffer|Bytes|Pixels|Samples|Frame|Audio|Image|Wave|PCM|RGBA?))\b"
)

TYPED_ARRAY_METHOD_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.(?P<method>set|fill|sort|reverse|copyWithin)\s*\("
)

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

URLSEARCHPARAMS_METHODS: tuple[str, ...] = ("append", "set", "delete", "sort")

URLSEARCHPARAMS_DECL_PATTERN = re.compile(r"new\s+URLSearchParams\s*\(")
URLSEARCHPARAMS_NAME_HINT_PATTERN = re.compile(
    r"\b(?:[a-zA-Z_$][\w$]*(?:Params|SearchParams|QueryString|QueryParams|Query))\b"
    r"|:\s*URLSearchParams\b"
)
URLSEARCHPARAMS_METHOD_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.(?P<method>"
    + "|".join(URLSEARCHPARAMS_METHODS)
    + r")\s*\("
)

HEADERS_METHODS: tuple[str, ...] = ("append", "set", "delete")

HEADERS_DECL_PATTERN = re.compile(r"new\s+Headers\s*\(")
HEADERS_NAME_HINT_PATTERN = re.compile(
    r"\b(?:[a-zA-Z_$][\w$]*(?:Headers|RequestHeaders|ResponseHeaders|HeadersInit))\b"
    r"|:\s*Headers\b"
)
HEADERS_METHOD_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.(?P<method>"
    + "|".join(HEADERS_METHODS)
    + r")\s*\("
)

FORMDATA_METHODS: tuple[str, ...] = ("append", "set", "delete")

FORMDATA_DECL_PATTERN = re.compile(r"new\s+FormData\s*\(")
FORMDATA_NAME_HINT_PATTERN = re.compile(
    r"\b(?:[a-zA-Z_$][\w$]*(?:FormData|formData))\b|:\s*FormData\b"
)
FORMDATA_METHOD_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.(?P<method>"
    + "|".join(FORMDATA_METHODS)
    + r")\s*\("
)


def _iter_lines(text: str) -> list[tuple[int, str, str]]:
    """Yield (lineno, raw, masked) tuples for each non-empty line.

    Masked content has string literals and comments replaced with whitespace
    so regex matches against `masked` cannot fire from inside strings.
    """
    out: list[tuple[int, str, str]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        out.append((idx, line, strip_strings_comments(line)))
    return out


def _make_match(
    detector: str,
    lineno: int,
    col: int,
    raw: str,
    fix_hint: str,
    metadata: dict[str, str] | None = None,
) -> Match:
    return Match(
        line=lineno,
        col=col + 1,
        text=truncate_excerpt(raw, 120),
        detector=detector,
        fix_hint=fix_hint,
        metadata=metadata or {},
    )


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


def detect_array_pop_shift_unshift_splice_reverse_fill_copywithin(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect array prototype mutations other than push and sort.

    Skips owners that are tracked Web API receivers (URLSearchParams,
    Headers, FormData) so the dedicated web-api detector emits the
    correct, more specific fix suggestion instead of the generic array
    advice.
    """
    results: list[Match] = []
    web_api_receivers = collect_web_api_receivers(text)
    for lineno, raw, masked in _iter_lines(text):
        for detector, pattern, fix_hint in _ARRAY_DETECTORS:
            for m in pattern.finditer(masked):
                owner = m.group("owner") or ""
                if is_web_api_receiver(owner, web_api_receivers):
                    continue
                results.append(
                    _make_match(
                        detector,
                        lineno,
                        m.start(),
                        raw,
                        fix_hint,
                        {"owner": owner},
                    )
                )
    return results


def detect_array_push(text: str, lang: str | None, file_path: str) -> list[Match]:
    """Detect `.push()` on a non-framework receiver.

    Framework navigation receivers and stream APIs are not flagged here;
    the orchestrator filters them via `mutation_allowlists.is_framework_receiver`.
    Web API receivers (URLSearchParams, Headers, FormData) cannot host
    `.push()`, but the dedup is included for symmetry with the other
    array detectors.
    """
    results: list[Match] = []
    fix_hint = (
        "Replace `arr.push(item)` with `arr = [...arr, item]` or include the new item directly: "
        "`return [...arr, item]`. For typed parameters, mark them `readonly T[]` to surface "
        "this at compile time. Framework navigation (router.push, history.push) is auto-allowed."
    )
    web_api_receivers = collect_web_api_receivers(text)
    for lineno, raw, masked in _iter_lines(text):
        for m in PUSH_PATTERN.finditer(masked):
            owner = m.group("owner") or ""
            if is_web_api_receiver(owner, web_api_receivers):
                continue
            results.append(
                _make_match(
                    "array.push",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"owner": owner, "raw_line": raw},
                )
            )
    return results


def detect_array_sort(text: str, lang: str | None, file_path: str) -> list[Match]:
    """Detect `.sort()` calls.

    Skips owners that are tracked URLSearchParams receivers because
    `params.sort()` is flagged separately by the web-api detector with
    a more specific fix suggestion.
    """
    results: list[Match] = []
    fix_hint = (
        "Replace `arr.sort(fn)` with `arr.toSorted(fn)` (ES2023) or `[...arr].sort(fn)`. "
        "For typed parameters, mark them `readonly T[]` to surface this at compile time."
    )
    web_api_receivers = collect_web_api_receivers(text)
    for lineno, raw, masked in _iter_lines(text):
        for m in SORT_PATTERN.finditer(masked):
            owner = m.group("owner") or ""
            if is_web_api_receiver(owner, web_api_receivers):
                continue
            results.append(
                _make_match(
                    "array.sort",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"owner": owner},
                )
            )
    return results


def detect_bracket_dispatch(text: str, lang: str | None, file_path: str) -> list[Match]:
    """Detect bracket-access dispatch like `arr['push'](x)`."""
    results: list[Match] = []
    fix_hint = (
        "Bracket-string dispatch (`arr['push'](x)`) bypasses static analysis and the spread-based "
        "alternative. Use the immutable equivalent for the underlying method (toSorted, toReversed, "
        "toSpliced, with). The dispatch pattern itself is a code smell separate from the mutation."
    )
    for lineno, raw, masked in _iter_lines(text):
        for m in BRACKET_DISPATCH_PATTERN.finditer(raw):
            owner_start = m.start()
            if owner_start < len(masked) and masked[owner_start] == " ":
                continue
            results.append(
                _make_match(
                    f"array.bracket-dispatch.{m.group('method')}",
                    lineno,
                    owner_start,
                    raw,
                    fix_hint,
                    {
                        "owner": m.group("owner") or "",
                        "method": m.group("method") or "",
                    },
                )
            )
    return results


def _collection_receiver_kind(window: str) -> str | None:
    """Best-effort guess of the receiver type from surrounding text."""
    if WEAKMAP_RECEIVER_HINT.search(window):
        return "WeakMap"
    if WEAKSET_RECEIVER_HINT.search(window):
        return "WeakSet"
    if MAP_RECEIVER_HINT.search(window):
        return "Map"
    if SET_RECEIVER_HINT.search(window):
        return "Set"
    return None


def detect_map_set_collection_mutations(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect Map / Set / WeakMap / WeakSet mutations.

    Receiver-kind heuristic looks at the surrounding 4-line window for a
    `new Map(...)` / `new Set(...)` declaration or a typed annotation
    (`: Map<K, V>`). When the heuristic is inconclusive the detector emits
    no hit so it stays conservative on unfamiliar code.

    Temporal API receivers are excluded: `t.add({ hours: 1 })` on a
    `Temporal.Now.instant()` value returns a new immutable Temporal,
    not a Set mutation.
    """
    results: list[Match] = []
    lines = text.splitlines()
    temporal_receivers = (
        collect_temporal_receivers(text) if has_temporal_usage(text) else frozenset()
    )
    web_api_receivers = collect_web_api_receivers(text)
    for lineno, raw, masked in _iter_lines(text):
        window = "\n".join(lines[max(0, lineno - 5) : lineno + 4])
        kind = _collection_receiver_kind(window)
        if not kind:
            continue
        if kind in ("Map", "WeakMap"):
            _emit_map_mutations(
                results,
                lineno,
                raw,
                masked,
                kind,
                temporal_receivers,
                web_api_receivers,
            )
        if kind in ("Set", "WeakSet"):
            _emit_set_mutations(
                results,
                lineno,
                raw,
                masked,
                kind,
                temporal_receivers,
                web_api_receivers,
            )
    return results


def _emit_map_mutations(
    results: list[Match],
    lineno: int,
    raw: str,
    masked: str,
    kind: str,
    temporal_receivers: frozenset[str] = frozenset(),
    web_api_receivers: frozenset[str] = frozenset(),
) -> None:
    set_fix = (
        f"Replace `{kind.lower()}.set(k, v)` with `new {kind}([...{kind.lower()}, [k, v]])`. "
        f"Mark the parameter `Readonly{kind}<K, V>` to enforce immutability at the type level."
        if kind == "Map"
        else "WeakMap mutation: WeakMaps cannot be iterated, so a new instance loses every existing entry. Confirm the lifetime is genuinely a fresh-instance flow before suppressing."
    )
    delete_fix = (
        f"Replace `{kind.lower()}.delete(k)` with `new {kind}([...{kind.lower()}].filter(([key]) => key !== k))`."
        if kind == "Map"
        else "WeakMap deletion is rare and may be intended. Document the lifetime; suppress with `// allow-mutation` plus a justification trailer."
    )
    clear_fix = (
        f"Replace `{kind.lower()}.clear()` with `new {kind}()` and reassign."
        if kind == "Map"
        else "WeakMaps cannot be cleared; the call is a no-op or a code smell. Investigate the intent."
    )
    for m in MAP_SET_PATTERN.finditer(masked):
        owner = m.group("owner")
        if is_temporal_chain_call(raw, owner, temporal_receivers):
            continue
        if is_web_api_receiver(owner, web_api_receivers):
            continue
        results.append(
            _make_match(
                f"collection.{kind.lower()}.set",
                lineno,
                m.start(),
                raw,
                set_fix,
                {"kind": kind},
            )
        )
    for m in MAP_DELETE_PATTERN.finditer(masked):
        owner = m.group("owner")
        if is_temporal_chain_call(raw, owner, temporal_receivers):
            continue
        if is_web_api_receiver(owner, web_api_receivers):
            continue
        results.append(
            _make_match(
                f"collection.{kind.lower()}.delete",
                lineno,
                m.start(),
                raw,
                delete_fix,
                {"kind": kind},
            )
        )
    if kind == "Map":
        for m in MAP_CLEAR_PATTERN.finditer(masked):
            owner = m.group("owner") if "owner" in (m.groupdict() or {}) else None
            if is_web_api_receiver(owner, web_api_receivers):
                continue
            results.append(
                _make_match(
                    f"collection.{kind.lower()}.clear",
                    lineno,
                    m.start(),
                    raw,
                    clear_fix,
                    {"kind": kind},
                )
            )


def _emit_set_mutations(
    results: list[Match],
    lineno: int,
    raw: str,
    masked: str,
    kind: str,
    temporal_receivers: frozenset[str] = frozenset(),
    web_api_receivers: frozenset[str] = frozenset(),
) -> None:
    add_fix = (
        f"Replace `{kind.lower()}.add(v)` with `new {kind}([...{kind.lower()}, v])`. "
        f"For lookups that must not grow, type the parameter as `Readonly{kind}<T>`."
        if kind == "Set"
        else "WeakSet mutation: WeakSets cannot be iterated, so a fresh instance loses every entry. Document the lifetime explicitly."
    )
    delete_fix = (
        f"Replace `{kind.lower()}.delete(v)` with `new {kind}([...{kind.lower()}].filter(x => x !== v))`."
        if kind == "Set"
        else "WeakSet deletion is rare. Suppress with `// allow-mutation` plus a justification trailer if the intent is correct."
    )
    clear_fix = (
        f"Replace `{kind.lower()}.clear()` with `new {kind}()` and reassign."
        if kind == "Set"
        else "WeakSets cannot be cleared; the call is a no-op."
    )
    for m in SET_ADD_PATTERN.finditer(masked):
        owner = m.group("owner")
        if is_temporal_chain_call(raw, owner, temporal_receivers):
            continue
        if is_web_api_receiver(owner, web_api_receivers):
            continue
        results.append(
            _make_match(
                f"collection.{kind.lower()}.add",
                lineno,
                m.start(),
                raw,
                add_fix,
                {"kind": kind},
            )
        )
    for m in MAP_DELETE_PATTERN.finditer(masked):
        owner = m.group("owner")
        if is_temporal_chain_call(raw, owner, temporal_receivers):
            continue
        if is_web_api_receiver(owner, web_api_receivers):
            continue
        results.append(
            _make_match(
                f"collection.{kind.lower()}.delete",
                lineno,
                m.start(),
                raw,
                delete_fix,
                {"kind": kind},
            )
        )
    if kind == "Set":
        for m in MAP_CLEAR_PATTERN.finditer(masked):
            results.append(
                _make_match(
                    f"collection.{kind.lower()}.clear",
                    lineno,
                    m.start(),
                    raw,
                    clear_fix,
                    {"kind": kind},
                )
            )


def detect_typed_array_mutations(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect TypedArray mutations on receivers that look like binary buffers.

    The orchestrator skips this detector when `is_hot_path(file_path)` is
    True, so crypto, codec, and image directories never trip it.
    """
    if not TYPED_ARRAY_DECL_PATTERN.search(
        text
    ) and not TYPED_ARRAY_NAME_HINT_PATTERN.search(text):
        return []
    results: list[Match] = []
    fix_hint = (
        "TypedArrays support ES2023 immutable methods: `arr.toSorted()`, `arr.toReversed()`, "
        "`arr.with(i, v)`. For `.set()` and `.fill()`, allocate a new TypedArray of the same "
        "constructor and copy. Hot paths (crypto, codec, image, audio, parser, wasm) are exempt; "
        "see ~/.claude/rules/code-style.md Immutability."
    )
    for lineno, raw, masked in _iter_lines(text):
        for m in TYPED_ARRAY_METHOD_PATTERN.finditer(masked):
            results.append(
                _make_match(
                    f"typed-array.{m.group('method')}",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {
                        "owner": m.group("owner") or "",
                        "method": m.group("method") or "",
                    },
                )
            )
    return results


def detect_date_setters(text: str, lang: str | None, file_path: str) -> list[Match]:
    """Detect Date prototype setter calls.

    Receiver name heuristic: the receiver identifier looks like a Date
    (`*Date`, `*time`, `*timestamp`, `*moment`, `*now`, etc.) or the file
    contains a `new Date(...)` initializer for the receiver. Conservative
    when no signal is present so custom calendar objects with a `setMonth`
    method are not flagged.

    Fix suggestions depend on whether the file uses the Temporal API.
    Files importing or referencing `Temporal.*` get a Temporal-first hint;
    other files get the date-fns fallback.
    """
    if not DATE_RECEIVER_HINT.search(text):
        return []
    results: list[Match] = []
    use_temporal = has_temporal_usage(text)
    if use_temporal:
        setter_fix = (
            "Date setters mutate the receiver. The file already uses Temporal; prefer "
            "`Temporal.PlainDate.from(d).with({ month: m })`, `instant.add({ hours: 1 })`, or "
            "`zoned.subtract({ days: 7 })`. Temporal returns are immutable. Rule: "
            "~/.claude/rules/code-style.md Date and Time Handling."
        )
        chain_fix = (
            "`new Date(d.setMonth(...))` mutates `d` AND uses the mutated value as a constructor "
            "argument; the resulting Date and the original now share state. The file uses Temporal; "
            "prefer `Temporal.PlainDate.from(d.toISOString()).with({ month: m })` or convert the "
            "Date upstream and stay in Temporal."
        )
    else:
        setter_fix = (
            "Date setters mutate the receiver. Use date-fns immutable helpers: `subMonths(d, 1)`, "
            "`addDays(d, 7)`, `setHours` from date-fns returns a new Date. The Temporal API "
            "(Stage 4 / ES2026) is the long-term replacement; consider adopting "
            "`@js-temporal/polyfill` for new code. Rule: "
            "~/.claude/rules/code-style.md Date and Time Handling."
        )
        chain_fix = (
            "`new Date(d.setMonth(...))` mutates `d` AND uses the mutated value as a constructor "
            "argument; the resulting Date and the original now share state. Use `addMonths(d, n)` "
            "or `setMonth(d, m)` from date-fns instead. Temporal API is Stage 4 / ES2026."
        )
    for lineno, raw, masked in _iter_lines(text):
        for m in DATE_CONSTRUCTOR_CHAIN_PATTERN.finditer(masked):
            results.append(
                _make_match("date.constructor-chain", lineno, m.start(), raw, chain_fix)
            )
        for m in DATE_SETTER_PATTERN.finditer(masked):
            results.append(
                _make_match(
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
            )
    return results


def _collect_typed_receivers(text: str, type_name: str) -> frozenset[str]:
    """Collect identifiers explicitly typed as `type_name` via `: TypeName` annotation.

    Captures `const x: URLSearchParams = ...`, `function f(p: Headers)`,
    `let h: FormData | null`, etc. Used to anchor mutation detection to
    receivers whose type is provable from the source.
    """
    pattern = re.compile(
        r"(?:const|let|var|function\s+\w+\s*\(|,|\()\s*"
        r"(?P<name>[a-zA-Z_$][\w$]*)\s*:\s*" + re.escape(type_name) + r"\b"
    )
    return frozenset(m.group("name") for m in pattern.finditer(text))


def _collect_constructed_receivers(text: str, type_name: str) -> frozenset[str]:
    """Collect identifiers initialized from `new TypeName(...)`.

    Captures `const x = new URLSearchParams(...)`, `let h = new Headers(...)`,
    `var fd = new FormData(...)`. Conservative: only matches direct `new`
    construction, not factory functions.
    """
    pattern = re.compile(
        r"(?:const|let|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*"
        r"(?::\s*[^=]+)?\s*=\s*new\s+" + re.escape(type_name) + r"\s*\("
    )
    return frozenset(m.group("name") for m in pattern.finditer(text))


def _detect_web_api_collection(
    text: str,
    type_name: str,
    detector_prefix: str,
    decl_pattern: re.Pattern[str],
    hint_pattern: re.Pattern[str],
    method_pattern: re.Pattern[str],
    fix_hint: str,
    confidence: str = "5",
) -> list[Match]:
    """Generic detector for Web API receiver-typed mutations.

    Triggers on a line-by-line scan when the text contains either a
    `new TypeName(...)` declaration, a typed annotation (`: TypeName`),
    or a name hint pattern. The receiver of the method call must match
    one of the typed or constructed receivers, OR the file must show
    enough usage signal to anchor the detector. Conservative: when no
    signal is present, the detector emits nothing.
    """
    if not decl_pattern.search(text) and not hint_pattern.search(text):
        return []
    typed = _collect_typed_receivers(text, type_name)
    constructed = _collect_constructed_receivers(text, type_name)
    anchored: frozenset[str] = typed | constructed
    has_strong_signal = bool(decl_pattern.search(text)) or bool(typed)
    results: list[Match] = []
    for lineno, raw, masked in _iter_lines(text):
        for m in method_pattern.finditer(masked):
            owner = m.group("owner") or ""
            if anchored:
                if owner not in anchored:
                    continue
            elif not has_strong_signal:
                continue
            results.append(
                _make_match(
                    f"{detector_prefix}.{m.group('method')}",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {
                        "owner": owner,
                        "method": m.group("method") or "",
                        "confidence": confidence,
                    },
                )
            )
    return results


def detect_url_search_params_mutations(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect URLSearchParams mutations.

    `URLSearchParams` is a Web API value with `append`, `set`, `delete`,
    and `sort` methods that mutate the instance. Non-mutating fix:
    construct a fresh instance from the existing entries plus the change.
    """
    fix_hint = (
        "URLSearchParams mutations: build a fresh instance instead of mutating in place. "
        "`new URLSearchParams([...params, [k, v]])` for append/set, "
        "`new URLSearchParams([...params].filter(([k]) => k !== removed))` for delete, "
        "`new URLSearchParams([...params].toSorted())` for sort. The existing instance is unchanged "
        "so other consumers of `params` see the original query string."
    )
    return _detect_web_api_collection(
        text,
        type_name="URLSearchParams",
        detector_prefix="web-api.url-search-params",
        decl_pattern=URLSEARCHPARAMS_DECL_PATTERN,
        hint_pattern=URLSEARCHPARAMS_NAME_HINT_PATTERN,
        method_pattern=URLSEARCHPARAMS_METHOD_PATTERN,
        fix_hint=fix_hint,
        confidence="5",
    )


def detect_headers_mutations(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect Headers (Fetch API) mutations.

    `Headers` instances expose `append`, `set`, and `delete`. Construct a
    fresh `Headers` from the existing entries instead of mutating.
    """
    fix_hint = (
        "Headers mutations: build a fresh instance. "
        "`new Headers([...headers, [name, value]])` for append/set, "
        "`new Headers([...headers].filter(([name]) => name.toLowerCase() !== removed.toLowerCase()))` "
        "for delete. Header names are case-insensitive; the filter must lowercase both sides."
    )
    return _detect_web_api_collection(
        text,
        type_name="Headers",
        detector_prefix="web-api.headers",
        decl_pattern=HEADERS_DECL_PATTERN,
        hint_pattern=HEADERS_NAME_HINT_PATTERN,
        method_pattern=HEADERS_METHOD_PATTERN,
        fix_hint=fix_hint,
        confidence="5",
    )


def detect_form_data_mutations(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect FormData mutations.

    `FormData` is a Web API value with `append`, `set`, `delete`. Some Web
    APIs (XHR.send, fetch body) require the same FormData instance, so the
    detector emits at confidence 3 (low). The fix hint covers both the
    fresh-instance pattern and the suppression marker for cases where
    instance identity is required.
    """
    fix_hint = (
        "FormData mutations: prefer a fresh instance via "
        "`Array.from(formData.entries()).reduce((fd, [k, v]) => { fd.append(k, v); return fd; }, new FormData())` "
        "with the change applied during construction, or build the entries array immutably first. "
        "When the API consumer requires a stable FormData reference (XHR.send keeps a pointer, "
        "third-party SDK retains the instance), suppress with `// @allow-mutation -- "
        "<reason>` and document why. Confidence: 3 (FormData is a frequent legitimate exception)."
    )
    return _detect_web_api_collection(
        text,
        type_name="FormData",
        detector_prefix="web-api.form-data",
        decl_pattern=FORMDATA_DECL_PATTERN,
        hint_pattern=FORMDATA_NAME_HINT_PATTERN,
        method_pattern=FORMDATA_METHOD_PATTERN,
        fix_hint=fix_hint,
        confidence="3",
    )


DATAVIEW_SETTERS: tuple[str, ...] = (
    "setInt8",
    "setUint8",
    "setInt16",
    "setUint16",
    "setInt32",
    "setUint32",
    "setBigInt64",
    "setBigUint64",
    "setFloat32",
    "setFloat64",
)

DATAVIEW_SETTER_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.(?P<method>"
    + "|".join(DATAVIEW_SETTERS)
    + r")\s*\("
)

DATAVIEW_DECL_PATTERN = re.compile(r"new\s+DataView\s*\(")
DATAVIEW_NAME_HINT_PATTERN = re.compile(
    r"\b(?:[a-zA-Z_$][\w$]*(?:View|DataView|dv))\b|:\s*DataView\b"
)


def detect_dataview_setters(text: str, lang: str | None, file_path: str) -> list[Match]:
    """Detect DataView mutating setters.

    `DataView` write methods (`setInt8`, `setUint8`, etc.) mutate the
    underlying `ArrayBuffer`. The buffer-backed nature makes this a
    legitimate operation in binary codecs, but other call sites should
    prefer constructing a fresh buffer or using typed-array slicing.

    Hot-path directories (crypto, codec, image, audio, wasm, parser,
    encoder, decoder, simd, fft, ml, tensor, signal, dsp) are skipped
    by the orchestrator. Outside those, the detector emits at
    confidence 4 (moderate, frequent legitimate exception via
    binary protocol authors).
    """
    fix_hint = (
        "DataView setters mutate the backing ArrayBuffer in place. When the operation is "
        "not inherently buffer-pointer-stable (codec, wire protocol, WASM linear memory), "
        "build a fresh `ArrayBuffer` of the required size and write to a new DataView, then "
        "publish the new buffer atomically. For SharedArrayBuffer, prefer `Atomics.store(...)` "
        "(also flagged but with the SAB-aware fix) so the write is ordered. Suppress with "
        "`// @allow-mutation -- <reason>` when the caller requires pointer stability."
    )
    masked = strip_strings_comments(text)
    context_signal = bool(
        DATAVIEW_DECL_PATTERN.search(masked)
        or DATAVIEW_NAME_HINT_PATTERN.search(masked)
    )
    if not context_signal:
        return []
    results: list[Match] = []
    for lineno, raw, line_masked in _iter_lines(text):
        for m in DATAVIEW_SETTER_PATTERN.finditer(line_masked):
            owner = m.group("owner") or ""
            method = m.group("method")
            results.append(
                _make_match(
                    "web-api.dataview." + method,
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"owner": owner, "method": method, "confidence": "4"},
                )
            )
    return results


ATOMICS_MUTATION_METHODS: tuple[str, ...] = (
    "store",
    "exchange",
    "compareExchange",
    "add",
    "sub",
    "and",
    "or",
    "xor",
)

ATOMICS_PATTERN = re.compile(
    r"\bAtomics\s*\.\s*(?P<method>" + "|".join(ATOMICS_MUTATION_METHODS) + r")\s*\("
)


def detect_atomics_mutations(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect `Atomics.*` mutating operations on SharedArrayBuffer views.

    `Atomics.store`, `exchange`, `compareExchange`, `add`, `sub`, `and`,
    `or`, `xor` write to shared memory and synchronize across workers.
    They are the correct primitive for SAB writes; the detector fires at
    info severity (confidence 2) so authors get an awareness ping without
    a block. Hot paths (wasm, simd, codec) are silent.

    `Atomics.load`, `Atomics.wait`, `Atomics.notify`, `Atomics.pause`
    are non-mutating and not flagged.
    """
    fix_hint = (
        "Atomics mutating ops write to shared memory. Confirm the write is intentional and "
        "ordered against the rest of the protocol. Prefer a single-writer pattern with a "
        "lock-free queue when possible. For one-shot publish, allocate a fresh SAB and swap "
        "the reference via a message rather than mutating in place. Info-level signal."
    )
    masked = strip_strings_comments(text)
    if not ATOMICS_PATTERN.search(masked):
        return []
    results: list[Match] = []
    for lineno, raw, line_masked in _iter_lines(text):
        for m in ATOMICS_PATTERN.finditer(line_masked):
            method = m.group("method")
            results.append(
                _make_match(
                    "shared-memory.atomics." + method,
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"method": method, "confidence": "2", "severity": "info"},
                )
            )
    return results


WASM_MEMORY_GROW_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.grow\s*\(")

WASM_MEMORY_HINT_PATTERN = re.compile(
    r"\b(?:WebAssembly\s*\.\s*Memory|memory|Memory|wasmMemory|linearMemory)\b"
)


def detect_wasm_memory_grow(text: str, lang: str | None, file_path: str) -> list[Match]:
    """Detect `WebAssembly.Memory.prototype.grow` calls.

    `memory.grow(n)` extends linear memory by `n` pages and may
    invalidate existing typed-array views over the buffer. Detection
    runs only when the file references `WebAssembly.Memory` or has an
    identifier hint suggesting a WASM memory. Confidence 5: this is a
    legitimate operation, but every call site must reattach views.
    """
    fix_hint = (
        "WebAssembly.Memory.grow extends the buffer and invalidates existing typed-array "
        "views. After grow, recreate every Int8Array/Uint8Array/etc. view from "
        "`memory.buffer`. Document the new pre-grow/post-grow boundary in code comments. "
        "Prefer growing in coarse steps to amortize view recreation cost."
    )
    masked = strip_strings_comments(text)
    if not WASM_MEMORY_HINT_PATTERN.search(masked):
        return []
    results: list[Match] = []
    for lineno, raw, line_masked in _iter_lines(text):
        if (
            not WASM_MEMORY_HINT_PATTERN.search(line_masked)
            and "memory" not in line_masked.lower()
        ):
            continue
        for m in WASM_MEMORY_GROW_PATTERN.finditer(line_masked):
            owner = m.group("owner") or ""
            if not (
                "memory" in owner.lower()
                or "wasm" in owner.lower()
                or owner == "Memory"
            ):
                continue
            results.append(
                _make_match(
                    "wasm.memory.grow",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"owner": owner, "confidence": "5"},
                )
            )
    return results


UINT8_SET_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.set\s*\(")

UINT8_NAME_HINT_PATTERN = re.compile(
    r"\bUint8Array\b|new\s+Uint8Array\s*\(|:\s*Uint8Array\b"
)


def detect_uint8array_set_buffer_offset(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect the two-argument form of `Uint8Array.prototype.set`.

    `view.set(source, byteOffset)` copies into the receiver at a given
    offset and is a frequent source of bugs when the offset is computed.
    The one-arg form `view.set(source)` is also mutating but is handled
    by `detect_typed_array_mutations`; this detector adds a stricter
    advisory for the two-arg variant because the offset is the dominant
    failure mode (off-by-one, wrong base).

    Hot-path directories suppress; otherwise confidence 5.
    """
    fix_hint = (
        "`view.set(source, offset)` mutates the receiver. Common errors: byte vs element "
        "offset confusion, source length exceeding remaining space, source aliasing the "
        "destination view. Prefer a fresh typed array built with `Uint8Array.of(...)` or "
        "`new Uint8Array(buffer.slice(...))` and concatenate. For codec hot paths, suppress "
        "with `// @allow-mutation -- codec` and audit the offset arithmetic."
    )
    masked = strip_strings_comments(text)
    if not UINT8_NAME_HINT_PATTERN.search(masked):
        return []
    results: list[Match] = []
    for lineno, raw, line_masked in _iter_lines(text):
        for m in UINT8_SET_PATTERN.finditer(line_masked):
            tail = line_masked[m.end() :]
            depth = 1
            comma_seen_at_depth_one = False
            for ch in tail:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        break
                elif ch == "," and depth == 1:
                    comma_seen_at_depth_one = True
                    break
            if not comma_seen_at_depth_one:
                continue
            owner = m.group("owner") or ""
            results.append(
                _make_match(
                    "typed-array.uint8.set-with-offset",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"owner": owner, "confidence": "5"},
                )
            )
    return results


PROXY_HANDLER_TRAP_PATTERN = re.compile(
    r"\b(?P<trap>set|deleteProperty|defineProperty|setPrototypeOf)\s*\("
)

PROXY_HANDLER_CONTEXT_PATTERN = re.compile(
    r"new\s+Proxy\s*\(|Proxy\.revocable\s*\(|handler\s*[:=]"
)


def detect_proxy_mutating_traps(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect mutating Proxy traps.

    A handler implementing `set`, `deleteProperty`, `defineProperty`, or
    `setPrototypeOf` exposes a mutating interface even when the proxy is
    documented as read-only. The detector requires the file to construct
    a Proxy or define a handler object so unrelated `set(...)` method
    calls do not trigger false positives.
    """
    fix_hint = (
        "Mutating Proxy traps (`set`, `deleteProperty`, `defineProperty`, `setPrototypeOf`) "
        "expose mutation to consumers. Prefer a copy-on-write strategy: the trap returns a "
        "new proxy wrapping the modified data, and the original stays untouched. When the "
        "Proxy is genuinely a mutable façade, document that contract in the handler's JSDoc "
        "and suppress with `// @allow-mutation -- proxy-mutable-facade <reason>`."
    )
    masked = strip_strings_comments(text)
    if not PROXY_HANDLER_CONTEXT_PATTERN.search(masked):
        return []
    results: list[Match] = []
    in_handler = False
    brace_depth = 0
    for lineno, raw, line_masked in _iter_lines(text):
        if PROXY_HANDLER_CONTEXT_PATTERN.search(line_masked):
            in_handler = True
            brace_depth = 0
        if in_handler:
            brace_depth += line_masked.count("{") - line_masked.count("}")
            for m in PROXY_HANDLER_TRAP_PATTERN.finditer(line_masked):
                trap = m.group("trap")
                results.append(
                    _make_match(
                        "proxy.trap." + trap,
                        lineno,
                        m.start(),
                        raw,
                        fix_hint,
                        {"trap": trap, "confidence": "4"},
                    )
                )
            if brace_depth <= 0 and "}" in line_masked:
                in_handler = False
    return results


WEAKREF_DEREF_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.deref\s*\(\s*\)\s*[?]?\.(?P<method>[a-zA-Z_$][\w$]*)\s*\("
)

WEAKREF_DECL_PATTERN = re.compile(r"new\s+WeakRef\s*\(")


def detect_weakref_then_mutate(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect `weakRef.deref().<mutating-method>()` chains.

    `WeakRef.deref()` returns the target if still alive. Mutating the
    target through the dereferenced handle is risky because the GC may
    collect the target between the check and the call. The detector
    fires when the method name matches a known mutating method.
    """
    mutating_methods = {
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
    fix_hint = (
        "Mutating through `weakRef.deref()` is unsafe: the GC can collect the target between "
        "your deref and the call. If the operation must succeed, hold a strong reference for "
        "the duration. If the operation is best-effort, check `const target = weakRef.deref(); "
        "if (target) { ... }` and treat absence as a no-op. Beyond safety, prefer non-mutating "
        "operations on the dereferenced value."
    )
    masked = strip_strings_comments(text)
    if (
        not WEAKREF_DECL_PATTERN.search(masked)
        and "WeakRef" not in masked
        and ".deref" not in masked
    ):
        return []
    results: list[Match] = []
    for lineno, raw, line_masked in _iter_lines(text):
        for m in WEAKREF_DEREF_PATTERN.finditer(line_masked):
            method = m.group("method")
            if method not in mutating_methods:
                continue
            owner = m.group("owner") or ""
            results.append(
                _make_match(
                    "weakref.deref-mutate." + method,
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"owner": owner, "method": method, "confidence": "5"},
                )
            )
    return results


FINALIZATION_REGISTRY_PATTERN = re.compile(r"new\s+FinalizationRegistry\s*\(")

FOR_AWAIT_HEADER_PATTERN = re.compile(
    r"\bfor\s+await\s*\(\s*(?:const|let|var)\s+(?P<binding>[a-zA-Z_$][\w$]*)"
)

PUSH_INSIDE_BODY_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.push\s*\(")

UINT8_BASE64_SETTER_METHODS: tuple[str, ...] = ("setFromBase64", "setFromHex")

UINT8_BASE64_SETTER_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.(?P<method>"
    + "|".join(UINT8_BASE64_SETTER_METHODS)
    + r")\s*\("
)

MAP_UPSERT_METHODS: tuple[str, ...] = ("getOrInsert", "getOrInsertComputed")

MAP_UPSERT_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.(?P<method>"
    + "|".join(MAP_UPSERT_METHODS)
    + r")\s*\("
)

ARRAYBUFFER_TRANSFER_METHODS: tuple[str, ...] = (
    "transfer",
    "transferToFixedLength",
)

ARRAYBUFFER_TRANSFER_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.(?P<method>"
    + "|".join(ARRAYBUFFER_TRANSFER_METHODS)
    + r")\s*\("
)

ARRAYBUFFER_RECEIVER_HINT = re.compile(
    r"\bArrayBuffer\b|new\s+ArrayBuffer\s*\(|:\s*ArrayBuffer\b"
)

OBJECT_GROUPBY_PATTERN = re.compile(r"\bObject\s*\.\s*groupBy\s*\(")
GROUPBY_BUCKET_PUSH_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\[\s*[^\]]+\]\s*\.push\s*\("
)


def detect_finalization_registry(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect `FinalizationRegistry` construction.

    `FinalizationRegistry` callbacks run at GC time with no ordering or
    timing guarantees. Mutating shared state from inside the callback
    creates non-deterministic state transitions. The detector is
    informational (confidence 1, info severity) and aims to flag the
    construction so the reviewer can audit the callback body.
    """
    fix_hint = (
        "FinalizationRegistry callbacks run at unpredictable GC moments. Keep the callback "
        "side-effect-minimal: log, close a file handle, or release a connection. Never mutate "
        "shared application state from the callback. Spec note: callbacks may not run at all "
        "if the registry itself is collected. Treat the callback as best-effort cleanup."
    )
    masked = strip_strings_comments(text)
    if not FINALIZATION_REGISTRY_PATTERN.search(masked):
        return []
    results: list[Match] = []
    for lineno, raw, line_masked in _iter_lines(text):
        for m in FINALIZATION_REGISTRY_PATTERN.finditer(line_masked):
            results.append(
                _make_match(
                    "finalization-registry.construct",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"confidence": "1", "severity": "info"},
                )
            )
    return results


def detect_for_await_push_pattern(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect `for await (const x of asyncIter) { result.push(x) }`.

    The legacy pattern materializes an async iterable by mutating an
    array. ES2024 `Array.fromAsync(asyncIter)` does this without
    mutation. The detector pairs a `for await` header with a `.push`
    call inside the same brace block.

    The detector is conservative: it fires only when both a `for await`
    header and a `.push` body exist in the same file. A more precise
    AST-based check is left to the type bridge.
    """
    fix_hint = (
        "Replace `for await (const x of asyncIter) { result.push(x) }` with "
        "`const result = await Array.fromAsync(asyncIter)` (ES2024). For a transformation, "
        "use `Array.fromAsync(asyncIter, x => transform(x))` which accepts a mapper. Once "
        "the runtime targets ES2025+, switch to AsyncIterator helpers: `asyncIter.map(fn).toArray()`."
    )
    iter_lines = _iter_lines(text)
    has_for_await = any(
        FOR_AWAIT_HEADER_PATTERN.search(masked) for _, _, masked in iter_lines
    )
    if not has_for_await:
        return []
    has_push = any(".push(" in masked for _, _, masked in iter_lines)
    if not has_push:
        return []
    results: list[Match] = []
    in_for_await = False
    brace_depth = 0
    for lineno, raw, line_masked in iter_lines:
        if FOR_AWAIT_HEADER_PATTERN.search(line_masked):
            in_for_await = True
            brace_depth = line_masked.count("{") - line_masked.count("}")
            continue
        if in_for_await:
            brace_depth += line_masked.count("{") - line_masked.count("}")
            for m in PUSH_INSIDE_BODY_PATTERN.finditer(line_masked):
                owner = m.group("owner") or ""
                results.append(
                    _make_match(
                        "async-iterable.for-await-push",
                        lineno,
                        m.start(),
                        raw,
                        fix_hint,
                        {"owner": owner, "confidence": "6"},
                    )
                )
            if brace_depth <= 0:
                in_for_await = False
    return results


def detect_uint8_base64_setter(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect `Uint8Array.prototype.setFromBase64` and `setFromHex`.

    These Stage 3 methods mutate the receiver in place. The static forms
    `Uint8Array.fromBase64(str)` and `Uint8Array.fromHex(str)` return
    fresh instances and should be preferred outside hot paths.
    """
    fix_hint = (
        "Stage 3 `Uint8Array.prototype.setFromBase64` and `setFromHex` mutate the receiver "
        "in place. Use the static forms `Uint8Array.fromBase64(str)` and `Uint8Array.fromHex(str)` "
        "which return fresh instances. The static forms also expose a `lastChunkHandling` option "
        "for partial input. Suppress with `// @allow-mutation -- <reason>` for streaming "
        "decode pipelines that intentionally write into a preallocated buffer."
    )
    iter_lines = _iter_lines(text)
    if not any(
        UINT8_BASE64_SETTER_PATTERN.search(masked) for _, _, masked in iter_lines
    ):
        return []
    results: list[Match] = []
    for lineno, raw, line_masked in iter_lines:
        for m in UINT8_BASE64_SETTER_PATTERN.finditer(line_masked):
            owner = m.group("owner") or ""
            method = m.group("method")
            results.append(
                _make_match(
                    "uint8.set-from-base64"
                    if method == "setFromBase64"
                    else "uint8.set-from-hex",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"owner": owner, "method": method, "confidence": "5"},
                )
            )
    return results


def detect_map_upsert(text: str, lang: str | None, file_path: str) -> list[Match]:
    """Detect `Map.prototype.getOrInsert` and `getOrInsertComputed` (Stage 4 Upsert).

    The Upsert proposal adds two methods to `Map.prototype` that look like
    queries but mutate the receiver: when the key is absent they insert
    the default (or the result of the factory) before returning it.
    Outside reducer or cache scopes this is an in-place mutation that
    should be expressed as `new Map([...m, [k, v]])` to keep the original
    untouched.
    """
    fix_hint = (
        "Stage 4 `Map.prototype.getOrInsert(key, default)` and "
        "`getOrInsertComputed(key, factory)` mutate the receiver when the key "
        "is missing. For immutable callers use "
        "`map.has(k) ? map.get(k) : default` over a fresh "
        "`new Map([...map, [k, default]])`. Suppress with "
        "`// allow-mutation -- upsert into a local cache` for "
        "memoization receivers."
    )
    iter_lines = _iter_lines(text)
    if not any(MAP_UPSERT_PATTERN.search(masked) for _, _, masked in iter_lines):
        return []
    if not MAP_RECEIVER_HINT.search(text):
        return []
    results: list[Match] = []
    for lineno, raw, line_masked in iter_lines:
        for m in MAP_UPSERT_PATTERN.finditer(line_masked):
            owner = m.group("owner") or ""
            method = m.group("method")
            detector = (
                "collection.map.get-or-insert"
                if method == "getOrInsert"
                else "collection.map.get-or-insert-computed"
            )
            results.append(
                _make_match(
                    detector,
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"owner": owner, "method": method, "confidence": "4"},
                )
            )
    return results


def detect_arraybuffer_transfer(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect `ArrayBuffer.prototype.transfer` / `transferToFixedLength`.

    Both methods return a new buffer AND detach the receiver: after the
    call `source.byteLength === 0` and every existing view over `source`
    raises `TypeError` on access. This is a mutation of the receiver's
    observable state even though the return value is fresh.
    """
    fix_hint = (
        "`ArrayBuffer.prototype.transfer()` and `transferToFixedLength()` "
        "detach the source buffer: `source.byteLength` becomes 0 and every "
        "view over `source` raises on access. If you need a resized copy "
        "without detaching, allocate a new buffer of the target size and "
        "copy bytes with `new Uint8Array(target).set(new Uint8Array(source))`. "
        "Suppress with `// @allow-mutation -- ownership handoff` when "
        "the detachment is the intent (worker postMessage transfer list, "
        "zero-copy SAB resize)."
    )
    iter_lines = _iter_lines(text)
    if not any(
        ARRAYBUFFER_TRANSFER_PATTERN.search(masked) for _, _, masked in iter_lines
    ):
        return []
    if not ARRAYBUFFER_RECEIVER_HINT.search(text):
        return []
    results: list[Match] = []
    for lineno, raw, line_masked in iter_lines:
        for m in ARRAYBUFFER_TRANSFER_PATTERN.finditer(line_masked):
            owner = m.group("owner") or ""
            method = m.group("method")
            results.append(
                _make_match(
                    "arraybuffer.transfer"
                    if method == "transfer"
                    else "arraybuffer.transfer-to-fixed-length",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"owner": owner, "method": method, "confidence": "5"},
                )
            )
    return results


def detect_object_groupby_push(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect `Object.groupBy(...)` followed by `.push` on a bucket.

    `Object.groupBy` returns a fresh record where each value is a fresh
    array, but downstream code that calls `.push` on a bucket value
    reverts to in-place mutation. Either materialize via spread or use
    `Map.groupBy` plus an immutable reducer.
    """
    fix_hint = (
        "`Object.groupBy(items, key)` returns a record whose buckets are "
        "arrays. Pushing into a bucket mutates that array and breaks the "
        "immutable contract of the helper. Use `Map.groupBy` plus a reducer "
        "that produces fresh arrays, or compute the buckets with "
        "`items.reduce((acc, x) => ({ ...acc, [k(x)]: [...(acc[k(x)] ?? []), x] }), {})`."
    )
    iter_lines = _iter_lines(text)
    if not OBJECT_GROUPBY_PATTERN.search(text):
        return []
    if not any(
        GROUPBY_BUCKET_PUSH_PATTERN.search(masked) for _, _, masked in iter_lines
    ):
        return []
    results: list[Match] = []
    for lineno, raw, line_masked in iter_lines:
        for m in GROUPBY_BUCKET_PUSH_PATTERN.finditer(line_masked):
            owner = m.group("owner") or ""
            results.append(
                _make_match(
                    "object.group-by-bucket-push",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"owner": owner, "confidence": "3"},
                )
            )
    return results
