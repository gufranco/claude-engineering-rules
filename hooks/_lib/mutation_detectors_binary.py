from __future__ import annotations

import re

from .mutation_detectors_core import Match, mask_text
from .mutation_scan_helpers import iter_stripped_lines, make_match

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

WASM_MEMORY_GROW_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.grow\s*\(")

WASM_MEMORY_HINT_PATTERN = re.compile(
    r"\b(?:WebAssembly\s*\.\s*Memory|memory|Memory|wasmMemory|linearMemory)\b"
)

UINT8_SET_PATTERN = re.compile(r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.set\s*\(")

UINT8_NAME_HINT_PATTERN = re.compile(
    r"\bUint8Array\b|new\s+Uint8Array\s*\(|:\s*Uint8Array\b"
)

UINT8_BASE64_SETTER_METHODS: tuple[str, ...] = ("setFromBase64", "setFromHex")

UINT8_BASE64_SETTER_PATTERN = re.compile(
    r"(?P<owner>[a-zA-Z_$][\w$]*)\s*\.(?P<method>"
    + "|".join(UINT8_BASE64_SETTER_METHODS)
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

_TYPED_ARRAY_FIX = (
    "TypedArrays support ES2023 immutable methods: `arr.toSorted()`, `arr.toReversed()`, "
    "`arr.with(i, v)`. For `.set()` and `.fill()`, allocate a new TypedArray of the same "
    "constructor and copy. Hot paths (crypto, codec, image, audio, parser, wasm) are exempt; "
    "see ~/.claude/rules/code-style.md Immutability."
)
_DATAVIEW_FIX = (
    "DataView setters mutate the backing ArrayBuffer in place. When the operation is "
    "not inherently buffer-pointer-stable (codec, wire protocol, WASM linear memory), "
    "build a fresh `ArrayBuffer` of the required size and write to a new DataView, then "
    "publish the new buffer atomically. For SharedArrayBuffer, prefer `Atomics.store(...)` "
    "(also flagged but with the SAB-aware fix) so the write is ordered. Suppress with "
    "a single builder function when the caller requires pointer stability."
)
_ATOMICS_FIX = (
    "Atomics mutating ops write to shared memory. Confirm the write is intentional and "
    "ordered against the rest of the protocol. Prefer a single-writer pattern with a "
    "lock-free queue when possible. For one-shot publish, allocate a fresh SAB and swap "
    "the reference via a message rather than mutating in place. Info-level signal."
)
_WASM_GROW_FIX = (
    "WebAssembly.Memory.grow extends the buffer and invalidates existing typed-array "
    "views. After grow, recreate every Int8Array/Uint8Array/etc. view from "
    "`memory.buffer`. Document the new pre-grow/post-grow boundary in code comments. "
    "Prefer growing in coarse steps to amortize view recreation cost."
)
_UINT8_SET_FIX = (
    "`view.set(source, offset)` mutates the receiver. Common errors: byte vs element "
    "offset confusion, source length exceeding remaining space, source aliasing the "
    "destination view. Prefer a fresh typed array built with `Uint8Array.of(...)` or "
    "`new Uint8Array(buffer.slice(...))` and concatenate. For codec hot paths, suppress "
    "inside a codec module and audit the offset arithmetic."
)
_UINT8_BASE64_FIX = (
    "Stage 3 `Uint8Array.prototype.setFromBase64` and `setFromHex` mutate the receiver "
    "in place. Use the static forms `Uint8Array.fromBase64(str)` and `Uint8Array.fromHex(str)` "
    "which return fresh instances. The static forms also expose a `lastChunkHandling` option "
    "for partial input. Streaming "
    "decode pipelines that intentionally write into a preallocated buffer."
)
_ARRAYBUFFER_TRANSFER_FIX = (
    "`ArrayBuffer.prototype.transfer()` and `transferToFixedLength()` "
    "detach the source buffer: `source.byteLength` becomes 0 and every "
    "view over `source` raises on access. If you need a resized copy "
    "without detaching, allocate a new buffer of the target size and "
    "copy bytes with `new Uint8Array(target).set(new Uint8Array(source))`. "
    "The handoff is the operation when "
    "the detachment is the intent (worker postMessage transfer list, "
    "zero-copy SAB resize)."
)


def detect_typed_array_mutations(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    if not TYPED_ARRAY_DECL_PATTERN.search(
        text
    ) and not TYPED_ARRAY_NAME_HINT_PATTERN.search(text):
        return []
    return [
        make_match(
            f"typed-array.{m.group('method')}",
            lineno,
            m.start(),
            raw,
            _TYPED_ARRAY_FIX,
            {"owner": m.group("owner") or "", "method": m.group("method") or ""},
        )
        for lineno, raw, masked in iter_stripped_lines(text)
        for m in TYPED_ARRAY_METHOD_PATTERN.finditer(masked)
    ]


def detect_dataview_setters(text: str, lang: str | None, file_path: str) -> list[Match]:
    masked = mask_text(text)
    if not (
        DATAVIEW_DECL_PATTERN.search(masked)
        or DATAVIEW_NAME_HINT_PATTERN.search(masked)
    ):
        return []
    return [
        make_match(
            "web-api.dataview." + m.group("method"),
            lineno,
            m.start(),
            raw,
            _DATAVIEW_FIX,
            {
                "owner": m.group("owner") or "",
                "method": m.group("method"),
                "confidence": "4",
            },
        )
        for lineno, raw, line_masked in iter_stripped_lines(text)
        for m in DATAVIEW_SETTER_PATTERN.finditer(line_masked)
    ]


def detect_atomics_mutations(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    if not ATOMICS_PATTERN.search(mask_text(text)):
        return []
    return [
        make_match(
            "shared-memory.atomics." + m.group("method"),
            lineno,
            m.start(),
            raw,
            _ATOMICS_FIX,
            {"method": m.group("method"), "confidence": "2", "severity": "info"},
        )
        for lineno, raw, line_masked in iter_stripped_lines(text)
        for m in ATOMICS_PATTERN.finditer(line_masked)
    ]


def _line_mentions_memory(line_masked: str) -> bool:
    return bool(WASM_MEMORY_HINT_PATTERN.search(line_masked)) or (
        "memory" in line_masked.lower()
    )


def _is_memory_owner(owner: str) -> bool:
    lowered = owner.lower()
    return "memory" in lowered or "wasm" in lowered or owner == "Memory"


def detect_wasm_memory_grow(text: str, lang: str | None, file_path: str) -> list[Match]:
    if not WASM_MEMORY_HINT_PATTERN.search(mask_text(text)):
        return []
    return [
        make_match(
            "wasm.memory.grow",
            lineno,
            m.start(),
            raw,
            _WASM_GROW_FIX,
            {"owner": m.group("owner") or "", "confidence": "5"},
        )
        for lineno, raw, line_masked in iter_stripped_lines(text)
        if _line_mentions_memory(line_masked)
        for m in WASM_MEMORY_GROW_PATTERN.finditer(line_masked)
        if _is_memory_owner(m.group("owner") or "")
    ]


def _has_offset_argument(tail: str) -> bool:
    depth = 1
    for ch in tail:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return False
        elif ch == "," and depth == 1:
            return True
    return False


def detect_uint8array_set_buffer_offset(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    if not UINT8_NAME_HINT_PATTERN.search(mask_text(text)):
        return []
    return [
        make_match(
            "typed-array.uint8.set-with-offset",
            lineno,
            m.start(),
            raw,
            _UINT8_SET_FIX,
            {"owner": m.group("owner") or "", "confidence": "5"},
        )
        for lineno, raw, line_masked in iter_stripped_lines(text)
        for m in UINT8_SET_PATTERN.finditer(line_masked)
        if _has_offset_argument(line_masked[m.end() :])
    ]


def detect_uint8_base64_setter(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    iter_lines = iter_stripped_lines(text)
    if not any(
        UINT8_BASE64_SETTER_PATTERN.search(masked) for _, _, masked in iter_lines
    ):
        return []
    return [
        make_match(
            "uint8.set-from-base64"
            if m.group("method") == "setFromBase64"
            else "uint8.set-from-hex",
            lineno,
            m.start(),
            raw,
            _UINT8_BASE64_FIX,
            {
                "owner": m.group("owner") or "",
                "method": m.group("method"),
                "confidence": "5",
            },
        )
        for lineno, raw, line_masked in iter_lines
        for m in UINT8_BASE64_SETTER_PATTERN.finditer(line_masked)
    ]


def detect_arraybuffer_transfer(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    iter_lines = iter_stripped_lines(text)
    if not any(
        ARRAYBUFFER_TRANSFER_PATTERN.search(masked) for _, _, masked in iter_lines
    ):
        return []
    if not ARRAYBUFFER_RECEIVER_HINT.search(text):
        return []
    return [
        make_match(
            "arraybuffer.transfer"
            if m.group("method") == "transfer"
            else "arraybuffer.transfer-to-fixed-length",
            lineno,
            m.start(),
            raw,
            _ARRAYBUFFER_TRANSFER_FIX,
            {
                "owner": m.group("owner") or "",
                "method": m.group("method"),
                "confidence": "5",
            },
        )
        for lineno, raw, line_masked in iter_lines
        for m in ARRAYBUFFER_TRANSFER_PATTERN.finditer(line_masked)
    ]
