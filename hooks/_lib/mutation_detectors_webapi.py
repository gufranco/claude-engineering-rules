from __future__ import annotations

import re
from dataclasses import dataclass

from .mutation_detectors_core import Match
from .mutation_scan_helpers import iter_stripped_lines, make_match

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


@dataclass(frozen=True)
class _WebApiSpec:
    type_name: str
    detector_prefix: str
    decl_pattern: re.Pattern[str]
    hint_pattern: re.Pattern[str]
    method_pattern: re.Pattern[str]
    fix_hint: str
    confidence: str


@dataclass(frozen=True)
class _Receivers:
    anchored: frozenset[str]
    fresh_accumulators: frozenset[str]
    has_strong_signal: bool


_URLSEARCHPARAMS_SPEC = _WebApiSpec(
    type_name="URLSearchParams",
    detector_prefix="web-api.url-search-params",
    decl_pattern=URLSEARCHPARAMS_DECL_PATTERN,
    hint_pattern=URLSEARCHPARAMS_NAME_HINT_PATTERN,
    method_pattern=URLSEARCHPARAMS_METHOD_PATTERN,
    fix_hint=(
        "URLSearchParams mutations: build a fresh instance instead of mutating in place. "
        "`new URLSearchParams([...params, [k, v]])` for append/set, "
        "`new URLSearchParams([...params].filter(([k]) => k !== removed))` for delete, "
        "`new URLSearchParams([...params].toSorted())` for sort. The existing instance is unchanged "
        "so other consumers of `params` see the original query string."
    ),
    confidence="5",
)

_HEADERS_SPEC = _WebApiSpec(
    type_name="Headers",
    detector_prefix="web-api.headers",
    decl_pattern=HEADERS_DECL_PATTERN,
    hint_pattern=HEADERS_NAME_HINT_PATTERN,
    method_pattern=HEADERS_METHOD_PATTERN,
    fix_hint=(
        "Headers mutations: build a fresh instance. "
        "`new Headers([...headers, [name, value]])` for append/set, "
        "`new Headers([...headers].filter(([name]) => name.toLowerCase() !== removed.toLowerCase()))` "
        "for delete. Header names are case-insensitive; the filter must lowercase both sides."
    ),
    confidence="5",
)

_FORMDATA_SPEC = _WebApiSpec(
    type_name="FormData",
    detector_prefix="web-api.form-data",
    decl_pattern=FORMDATA_DECL_PATTERN,
    hint_pattern=FORMDATA_NAME_HINT_PATTERN,
    method_pattern=FORMDATA_METHOD_PATTERN,
    fix_hint=(
        "FormData mutations: prefer a fresh instance via "
        "`Array.from(formData.entries()).reduce((fd, [k, v]) => { fd.append(k, v); return fd; }, new FormData())` "
        "with the change applied during construction, or build the entries array immutably first. "
        "When the API consumer requires a stable FormData reference (XHR.send keeps a pointer, "
        "third-party SDK retains the instance), isolate the mutation in one builder "
        "function. Confidence: 3 (FormData is a frequent legitimate exception)."
    ),
    confidence="3",
)


def _collect_typed_receivers(text: str, type_name: str) -> frozenset[str]:
    pattern = re.compile(
        r"(?:const|let|var|function\s+\w+\s*\(|,|\()\s*"
        r"(?P<name>[a-zA-Z_$][\w$]*)\s*:\s*" + re.escape(type_name) + r"\b"
    )
    return frozenset(m.group("name") for m in pattern.finditer(text))


def _collect_constructed_receivers(text: str, type_name: str) -> frozenset[str]:
    pattern = re.compile(
        r"(?:const|let|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*"
        r"(?::\s*[^=]+)?\s*=\s*new\s+" + re.escape(type_name) + r"\s*\("
    )
    return frozenset(m.group("name") for m in pattern.finditer(text))


def _collect_fresh_reducer_accumulators(text: str, type_name: str) -> frozenset[str]:
    pattern = re.compile(
        r"\.reduce\s*\(\s*(?:async\s*)?\(\s*(?P<acc>[a-zA-Z_$][\w$]*)"
        r"[^)]*\)\s*=>.*?,\s*new\s+" + re.escape(type_name) + r"\s*\(",
        re.DOTALL,
    )
    return frozenset(m.group("acc") for m in pattern.finditer(text))


def _collect_receivers(text: str, spec: _WebApiSpec) -> _Receivers:
    typed = _collect_typed_receivers(text, spec.type_name)
    constructed = _collect_constructed_receivers(text, spec.type_name)
    return _Receivers(
        anchored=typed | constructed,
        fresh_accumulators=_collect_fresh_reducer_accumulators(text, spec.type_name),
        has_strong_signal=bool(spec.decl_pattern.search(text)) or bool(typed),
    )


def _owner_is_flagged(owner: str, receivers: _Receivers) -> bool:
    if owner and owner in receivers.fresh_accumulators:
        return False
    if receivers.anchored:
        return owner in receivers.anchored
    return receivers.has_strong_signal


def _web_api_match(spec: _WebApiSpec, lineno: int, raw: str, m: re.Match[str]) -> Match:
    return make_match(
        f"{spec.detector_prefix}.{m.group('method')}",
        lineno,
        m.start(),
        raw,
        spec.fix_hint,
        {
            "owner": m.group("owner") or "",
            "method": m.group("method") or "",
            "confidence": spec.confidence,
        },
    )


def _detect_web_api_collection(text: str, spec: _WebApiSpec) -> list[Match]:
    if not spec.decl_pattern.search(text) and not spec.hint_pattern.search(text):
        return []
    receivers = _collect_receivers(text, spec)
    return [
        _web_api_match(spec, lineno, raw, m)
        for lineno, raw, masked in iter_stripped_lines(text)
        for m in spec.method_pattern.finditer(masked)
        if _owner_is_flagged(m.group("owner") or "", receivers)
    ]


def detect_url_search_params_mutations(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return _detect_web_api_collection(text, _URLSEARCHPARAMS_SPEC)


def detect_headers_mutations(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return _detect_web_api_collection(text, _HEADERS_SPEC)


def detect_form_data_mutations(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    return _detect_web_api_collection(text, _FORMDATA_SPEC)
