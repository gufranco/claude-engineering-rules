from __future__ import annotations

import re

from .mutation_allowlist_names import (
    DOM_PROPERTY_NAMES,
    DOM_RECEIVER_NAMES,
    DOM_TYPED_RECEIVER_PATTERN,
    ES2024_STATIC_NON_MUTATING_FACTORIES,
    PARAM_REASSIGN_ALLOWLIST,
    TEMPORAL_FACTORY_VAR_DECL_PATTERN,
    TEMPORAL_IMPORT_PATTERN,
    TEMPORAL_TYPED_NAME_PATTERN,
    TEMPORAL_USAGE_PATTERN,
    WEB_API_TYPED_RECEIVER_TYPES,
)
from .mutation_state_patterns import (
    STATE_MGMT_FILENAME_PATTERNS,
    SVELTE_STATE_RAW_VAR_DECL_PATTERN,
)
from .mutation_state_rules import RECEIVER_RULES as _RECEIVER_RULES
from .mutation_state_rules import SCOPE_RULES as _SCOPE_RULES

JS_EXTS: tuple[str, ...] = (
    ".ts",
    ".tsx",
    ".mts",
    ".cts",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
)
TS_EXTS: tuple[str, ...] = (".ts", ".tsx", ".mts", ".cts")

SKIP_SEGMENTS: tuple[str, ...] = (
    "/scripts/",
    "/bin/",
    "/tools/",
    "/cli/",
    "/__tests__/",
    "/__test__/",
    "/.claude/hooks/",
    "/test-utils/",
    "/testing/",
    "/migrations/",
    "/seed",
    "/e2e/",
    "/fixtures/",
)

SKIP_SUFFIXES: tuple[str, ...] = (
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
    ".config.ts",
    ".config.js",
    ".config.mjs",
    ".stories.ts",
    ".stories.tsx",
    ".d.ts",
)

HOT_PATH_SEGMENTS: tuple[str, ...] = (
    "/crypto/",
    "/crypt/",
    "/cipher/",
    "/hash/",
    "/image/",
    "/images/",
    "/audio/",
    "/media/",
    "/parser/",
    "/decoder/",
    "/encoder/",
    "/codec/",
    "/webgl/",
    "/canvas/",
    "/pixel/",
    "/simd/",
    "/wasm/",
    "/bench/",
    "/benchmark/",
    "/dsp/",
    "/signal/",
    "/fft/",
    "/ml/",
    "/tensor/",
    "/webassembly/",
    "/wgpu/",
    "/webgpu/",
)

TYPED_ARRAY_SUBTYPES: tuple[str, ...] = (
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

THIRD_PARTY_COMMAND_QUEUES: frozenset[str] = frozenset(
    {
        "dataLayer",
        "dgEvent",
        "_paq",
        "_hsq",
        "_gaq",
        "_mtm",
        "uetq",
    }
)


PUSH_FRAMEWORK_RECEIVERS: frozenset[str] = frozenset(
    {
        "router",
        "Router",
        "routerRef",
        "navigation",
        "nav",
        "history",
        "pathname",
        "location",
        "stream",
        "streams",
        "Readable",
        "Writable",
        "Duplex",
        "Transform",
        "PassThrough",
        "res",
        "response",
        "ws",
        "socket",
        "client",
    }
    | THIRD_PARTY_COMMAND_QUEUES
)

PUSH_FRAMEWORK_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(re.escape(name) for name in PUSH_FRAMEWORK_RECEIVERS)
    + r")(?:\.current)?\.push\b"
)

PUSH_CALL_PATTERN = re.compile(r"\.push\b")

_DOM_ACCESSOR_SUFFIXES = (
    ".target",
    ".currentTarget",
    ".parentNode",
    ".parentElement",
    ".firstChild",
    ".lastChild",
    ".firstElementChild",
    ".lastElementChild",
    ".nextSibling",
    ".previousSibling",
    ".style",
    ".classList",
    ".dataset",
    ".attributes",
)

_TEMPORAL_CHAIN_PATTERN = re.compile(
    r"Temporal\.(?:Now|Instant|PlainDate|PlainTime|PlainDateTime|"
    r"PlainMonthDay|PlainYearMonth|ZonedDateTime|Duration)\."
)

_WEB_API_RECEIVER_PATTERNS: tuple[tuple[str, re.Pattern[str], re.Pattern[str]], ...] = (
    tuple(
        (
            type_name,
            re.compile(
                r"(?:const|let|var|function\s+\w+\s*\(|,|\()\s*"
                r"(?P<name>[a-zA-Z_$][\w$]*)\s*:\s*" + re.escape(type_name) + r"\b"
            ),
            re.compile(
                r"(?:const|let|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*"
                r"(?::\s*[^=]+)?\s*=\s*new\s+" + re.escape(type_name) + r"\s*\("
            ),
        )
        for type_name in WEB_API_TYPED_RECEIVER_TYPES
    )
)

_FILENAME_SCOPE_LABEL = "state-mgmt-filename"


def is_dom_receiver(receiver: str | None) -> bool:
    if not receiver:
        return False
    short = receiver.strip()
    if not short:
        return False
    last = short.rsplit(".", maxsplit=1)[-1]
    if last in DOM_RECEIVER_NAMES or DOM_TYPED_RECEIVER_PATTERN.match(last):
        return True
    return "." in short and short.endswith(_DOM_ACCESSOR_SUFFIXES)


def is_dom_assignment(receiver: str | None, prop: str | None) -> bool:
    if is_dom_receiver(receiver):
        return True
    return bool(prop) and prop in DOM_PROPERTY_NAMES


def has_temporal_usage(full_text: str) -> bool:
    if not full_text:
        return False
    if TEMPORAL_IMPORT_PATTERN.search(full_text):
        return True
    return bool(TEMPORAL_USAGE_PATTERN.search(full_text))


def collect_temporal_receivers(full_text: str) -> frozenset[str]:
    if not full_text:
        return frozenset()
    patterns = (TEMPORAL_FACTORY_VAR_DECL_PATTERN, TEMPORAL_TYPED_NAME_PATTERN)
    return frozenset(m.group(1) for p in patterns for m in p.finditer(full_text))


def is_temporal_chain_call(
    line: str, owner: str | None, receivers: frozenset[str]
) -> bool:
    if owner and owner in receivers:
        return True
    if not line:
        return False
    return "Temporal." in line and bool(_TEMPORAL_CHAIN_PATTERN.search(line))


def collect_web_api_receivers(full_text: str) -> frozenset[str]:
    if not full_text:
        return frozenset()
    return frozenset(
        m.group("name")
        for _type_name, typed, constructed in _WEB_API_RECEIVER_PATTERNS
        for pattern in (typed, constructed)
        for m in pattern.finditer(full_text)
    )


def is_web_api_receiver(owner: str | None, receivers: frozenset[str]) -> bool:
    if not owner:
        return False
    return owner in receivers


def is_es2024_static_factory(line: str) -> bool:
    if not line:
        return False
    return any(
        f"{factory}(" in line for factory in ES2024_STATIC_NON_MUTATING_FACTORIES
    )


def collect_state_mgmt_receivers(
    full_text: str, file_path: str
) -> dict[str, frozenset[str]]:
    if not full_text:
        return {}
    collected = {
        label: frozenset(m.group(1) for p in decls for m in p.finditer(full_text))
        for label, gate, decls in _RECEIVER_RULES
        if gate(full_text, file_path)
    }
    return {label: names for label, names in collected.items() if names}


def hit_uses_receiver(hit_line: str, receivers: frozenset[str]) -> bool:
    if not hit_line or not receivers:
        return False
    for name in receivers:
        if not name:
            continue
        if f"{name}." in hit_line and (
            f" {name}." in hit_line
            or hit_line.startswith(f"{name}.")
            or f"({name}." in hit_line
            or f"\t{name}." in hit_line
            or f"={name}." in hit_line
        ):
            return True
        pattern = re.compile(rf"(?:^|[^\w$]){re.escape(name)}(?:[^\w$.]|$)")
        if pattern.search(hit_line):
            return True
    return False


def skip_extension(file_path: str) -> bool:
    if not file_path:
        return True
    return not file_path.lower().endswith(JS_EXTS)


def skip_path(file_path: str) -> bool:
    if not file_path:
        return True
    p = file_path.lower()
    if any(seg in p for seg in SKIP_SEGMENTS):
        return True
    if any(p.endswith(suf) for suf in SKIP_SUFFIXES):
        return True
    return False


def is_hot_path(file_path: str) -> bool:
    if not file_path:
        return False
    p = file_path.lower()
    return any(seg in p for seg in HOT_PATH_SEGMENTS)


def is_framework_receiver(line: str, owner: str | None) -> bool:
    if owner and owner in PUSH_FRAMEWORK_RECEIVERS:
        return True
    framework = PUSH_FRAMEWORK_PATTERN.findall(line)
    return bool(framework) and len(framework) == len(PUSH_CALL_PATTERN.findall(line))


def collect_svelte_state_raw_receivers(full_text: str) -> frozenset[str]:
    return frozenset(
        m.group(1) for m in SVELTE_STATE_RAW_VAR_DECL_PATTERN.finditer(full_text)
    )


def is_state_mgmt_filename(file_path: str) -> bool:
    if not file_path:
        return False
    return any(pat.search(file_path) for pat in STATE_MGMT_FILENAME_PATTERNS)


def is_in_state_mgmt_scope(window: str, file_path: str) -> tuple[bool, str | None]:
    if not window:
        return False, None
    label = next(
        (label for label, rule in _SCOPE_RULES if rule(window, file_path)), None
    )
    if label is not None:
        return True, label
    if is_state_mgmt_filename(file_path):
        return True, _FILENAME_SCOPE_LABEL
    return False, None


def is_param_reassign_allowed_name(name: str) -> bool:
    return name in PARAM_REASSIGN_ALLOWLIST
