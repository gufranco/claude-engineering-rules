"""Source-map awareness for mutation-method-blocker (plan item 389).

When the hook analyzes transpiled output (`dist/`, `build/`, `out/`, or
any file with a `.map` sibling), it parses the source map and reports
findings against the original source location. Without source-map
support, transpiled findings are unactionable because the reviewer
sees minified or compiled output, not the source they wrote.

Public API:

    is_transpiled_path(file_path) -> bool
    load_source_map(file_path) -> dict | None
    map_to_original(source_map, line, col) -> tuple[str, int, int] | None

Design notes:

  - VLQ decoding is implemented inline to avoid an external dep. The
    source-map format uses base64 VLQ for compact line/column data.
  - Fail open: any parse error returns `None` and the original location
    is used. A broken source map never blocks a finding.
  - Caching: maps are read once per file path and cached for the
    process lifetime.
"""

from __future__ import annotations

import json
import os
from typing import Any

_TRANSPILED_DIRS: frozenset[str] = frozenset(
    {"dist", "build", "out", "lib", ".next", ".nuxt"}
)
_BASE64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_BASE64_INDEX: dict[str, int] = {ch: i for i, ch in enumerate(_BASE64_CHARS)}

_SOURCE_MAP_CACHE: dict[str, dict[str, Any] | None] = {}


def is_transpiled_path(file_path: str) -> bool:
    """Return True when the file looks like transpiled output."""
    if not file_path:
        return False
    parts = file_path.replace("\\", "/").split("/")
    return any(part in _TRANSPILED_DIRS for part in parts)


def _decode_vlq(segment: str) -> list[int]:
    """Decode a base64 VLQ segment into a list of integers."""
    values: list[int] = []
    value = 0
    shift = 0
    for ch in segment:
        if ch not in _BASE64_INDEX:
            return values
        digit = _BASE64_INDEX[ch]
        cont = digit & 0x20
        digit = digit & 0x1F
        value += digit << shift
        if cont:
            shift += 5
            continue
        magnitude = value >> 1
        negative = (value & 1) == 1
        result = -magnitude if negative else magnitude
        values.append(result)
        value = 0
        shift = 0
    return values


def _parse_mappings(mappings: str) -> list[list[list[int]]]:
    """Decode the `mappings` field into a 2D structure of segments.

    Returns lines, each containing a list of segments. Each segment is
    a list of 1, 4, or 5 integers per the source-map spec.
    """
    lines: list[list[list[int]]] = []
    prev = [0, 0, 0, 0, 0]
    prev_gen_col = 0
    for line_str in mappings.split(";"):
        segments: list[list[int]] = []
        prev_gen_col = 0
        for seg_str in line_str.split(","):
            if not seg_str:
                continue
            deltas = _decode_vlq(seg_str)
            if not deltas:
                continue
            seg = list(deltas)
            seg[0] = prev_gen_col + seg[0]
            prev_gen_col = seg[0]
            if len(seg) >= 4:
                seg[1] = prev[1] + (deltas[1] if len(deltas) > 1 else 0)
                seg[2] = prev[2] + (deltas[2] if len(deltas) > 2 else 0)
                seg[3] = prev[3] + (deltas[3] if len(deltas) > 3 else 0)
                prev[1] = seg[1]
                prev[2] = seg[2]
                prev[3] = seg[3]
            segments.append(seg)
        lines.append(segments)
    return lines


def load_source_map(file_path: str) -> dict[str, Any] | None:
    """Read and parse a `.map` sibling. Returns None when absent or invalid."""
    if file_path in _SOURCE_MAP_CACHE:
        return _SOURCE_MAP_CACHE[file_path]
    map_path = file_path + ".map"
    if not os.path.exists(map_path):
        _SOURCE_MAP_CACHE[file_path] = None
        return None
    try:
        with open(map_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        _SOURCE_MAP_CACHE[file_path] = None
        return None
    if not isinstance(data, dict) or "mappings" not in data:
        _SOURCE_MAP_CACHE[file_path] = None
        return None
    try:
        decoded = _parse_mappings(data["mappings"])
    except (TypeError, ValueError):
        _SOURCE_MAP_CACHE[file_path] = None
        return None
    bundle = {
        "sources": data.get("sources", []),
        "sourceRoot": data.get("sourceRoot", ""),
        "decoded": decoded,
    }
    _SOURCE_MAP_CACHE[file_path] = bundle
    return bundle


def map_to_original(
    source_map: dict[str, Any], line: int, col: int
) -> tuple[str, int, int] | None:
    """Map a generated (line, col) to the original (file, line, col).

    Lines are 1-based; columns are 0-based. Returns None when no mapping
    is found.
    """
    decoded = source_map.get("decoded") or []
    if line < 1 or line > len(decoded):
        return None
    segments = decoded[line - 1]
    if not segments:
        return None
    best = None
    for seg in segments:
        if len(seg) < 4:
            continue
        if seg[0] <= col:
            best = seg
        else:
            break
    if best is None:
        return None
    source_idx = best[1]
    orig_line = best[2] + 1
    orig_col = best[3]
    sources = source_map.get("sources") or []
    if source_idx < 0 or source_idx >= len(sources):
        return None
    source_root = source_map.get("sourceRoot") or ""
    source_path = sources[source_idx]
    if source_root and not source_path.startswith(
        ("/", "http://", "https://", "file://")
    ):
        joined = source_root.rstrip("/") + "/" + source_path
    else:
        joined = source_path
    return joined, orig_line, orig_col
