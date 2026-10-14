from __future__ import annotations

import re

DOM_RECEIVER_NAMES: frozenset[str] = frozenset(
    {
        "document",
        "body",
        "head",
        "html",
        "window",
        "self",
        "navigator",
        "screen",
        "history",
        "location",
        "element",
        "el",
        "node",
        "target",
        "currentTarget",
        "parent",
        "parentNode",
        "parentElement",
        "child",
        "childNode",
        "sibling",
        "root",
        "container",
        "wrapper",
        "host",
        "shadowRoot",
        "canvas",
        "ctx",
        "context2d",
        "context3d",
        "audio",
        "video",
        "img",
        "image",
        "form",
        "input",
        "button",
        "anchor",
        "link",
        "iframe",
        "ref",
        "domRef",
    }
)

DOM_TYPED_RECEIVER_PATTERN = re.compile(
    r".*(?:Element|HTMLElement|Node|Target|Btn|Button|Input|Img|Ref|Canvas|Anchor|Iframe|El)$"
)

DOM_PROPERTY_NAMES: frozenset[str] = frozenset(
    {
        "innerHTML",
        "outerHTML",
        "innerText",
        "outerText",
        "textContent",
        "className",
        "tabIndex",
        "scrollTop",
        "scrollLeft",
        "contentEditable",
        "spellcheck",
        "ariaLabel",
        "ariaHidden",
        "ariaDescribedBy",
        "ariaLabelledBy",
    }
)


TEMPORAL_IMPORT_PATTERN = re.compile(
    r"""['"](?:@js-temporal/polyfill|temporal-polyfill)['"]"""
)
TEMPORAL_USAGE_PATTERN = re.compile(
    r"\bTemporal\.(?:Now|Instant|PlainDate|PlainTime|PlainDateTime|"
    r"PlainMonthDay|PlainYearMonth|ZonedDateTime|Duration|TimeZone|Calendar)\b"
)
TEMPORAL_FACTORY_VAR_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)"
    r"(?:\s*:\s*[^=]+)?\s*=\s*"
    r"Temporal\.(?:Now\.(?:instant|zonedDateTimeISO|plainDateISO|"
    r"plainTimeISO|plainDateTimeISO)\s*\(|"
    r"(?:Instant|PlainDate|PlainTime|PlainDateTime|PlainMonthDay|"
    r"PlainYearMonth|ZonedDateTime|Duration)\.(?:from|fromEpoch[A-Za-z]+)\s*\()"
)
TEMPORAL_TYPED_NAME_PATTERN = re.compile(
    r"\b([a-zA-Z_$][\w$]*)\s*:\s*Temporal\.(?:Instant|PlainDate|PlainTime|"
    r"PlainDateTime|PlainMonthDay|PlainYearMonth|ZonedDateTime|Duration)\b"
)
TEMPORAL_IMMUTABLE_METHODS: frozenset[str] = frozenset(
    {
        "add",
        "subtract",
        "with",
        "withCalendar",
        "withTimeZone",
        "withPlainDate",
        "withPlainTime",
        "until",
        "since",
        "round",
        "equals",
        "compare",
        "toPlainDate",
        "toPlainTime",
        "toPlainDateTime",
        "toPlainYearMonth",
        "toPlainMonthDay",
        "toZonedDateTime",
        "toInstant",
        "toString",
        "toJSON",
        "toLocaleString",
        "valueOf",
        "getISOFields",
        "negated",
        "abs",
        "total",
    }
)


ES2024_STATIC_NON_MUTATING_FACTORIES: frozenset[str] = frozenset(
    {
        "Promise.withResolvers",
        "Promise.try",
        "Array.fromAsync",
        "RegExp.escape",
        "Atomics.pause",
        "Error.isError",
        "Object.groupBy",
        "Map.groupBy",
        "Iterator.from",
    }
)


WEB_API_TYPED_RECEIVER_TYPES: tuple[str, ...] = (
    "URLSearchParams",
    "Headers",
    "FormData",
)


PARAM_REASSIGN_ALLOWLIST: frozenset[str] = frozenset(
    {
        "acc",
        "accumulator",
        "result",
        "ctx",
        "context",
        "req",
        "request",
        "res",
        "response",
        "next",
        "e",
        "event",
        "draft",
    }
)
