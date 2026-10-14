from __future__ import annotations

import re
from dataclasses import dataclass

from .mutation_detectors_core import Match, mask_lines
from .mutation_scan_helpers import iter_masked_lines, looks_like_declaration, make_match

LET_DECL_PATTERN = re.compile(
    r"^\s*(?:export\s+)?let\s+(?P<name>[a-zA-Z_$][\w$]*)(?:\s*:\s*[^=;]+)?\s*=\s*"
)

LET_NO_INIT_PATTERN = re.compile(
    r"^\s*(?:export\s+)?let\s+(?P<name>[a-zA-Z_$][\w$]*)\s*(?::\s*[^=;]+)?\s*;\s*$"
)

LET_FOR_HEAD_PATTERN = re.compile(r"\bfor\s*\(\s*let\s+")

PARAM_REASSIGN_FN_PATTERN = re.compile(
    r"\bfunction\s+[a-zA-Z_$][\w$]*\s*\(\s*(?P<params>[^)]*)\)|"
    r"\(\s*(?P<arrow_params>[^)]*)\)\s*=>"
)

KNOWN_PROP_REASSIGN_PARAM_NAMES: frozenset[str] = frozenset(
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

STATIC_BLOCK_OPEN_PATTERN = re.compile(r"\bstatic\s*\{")

_CLASS_DECL_PATTERN = re.compile(r"\bclass\s+[A-Z][\w$]*")
_BRANCH_KEYWORD_PATTERN = re.compile(r"\b(if|else|switch|for|while|try|catch)\b")
_FUNCTION_HEADER_PATTERN = re.compile(r"^\s*function\b")
_CALL_HEADER_PATTERN = re.compile(r"^\s*[a-zA-Z_$][\w$]*\s*\(")
_PARAM_NAME_PATTERN = re.compile(r"^([a-zA-Z_$][\w$]*)\s*[?:]?")
_NON_PARAM_KEYWORDS = ("function", "async", "static", "return", "this")

_CANONICAL_FILTERED_DETECTORS: frozenset[str] = frozenset(
    {
        "property.assignment",
        "property.computed",
        "property.compound",
        "property.compound-index",
        "property.increment",
        "property.increment-prefix",
        "delete-operator",
        "object.assign",
        "reflect.set",
        "reflect.setPrototypeOf",
    }
)

_PARAM_REASSIGN_FIX = (
    "Never mutate function arguments. Copy at function entry: "
    "`const localOpts = { ...opts };`. Or accept the parameter as `Readonly<T>` and "
    'return a new object. Rule: ~/.claude/standards/code-style.md "Immutability".'
)
_LET_FIX = (
    "`let` that is never reassigned must be `const`. Rule: "
    '~/.claude/standards/typescript-immutability.md "Behavioral Rules".'
)
_STATIC_BLOCK_FIX = (
    "Class `static {}` blocks should perform one-time initialization in a single "
    "sequential block. If the logic needs branching, extract a factory function "
    "and assign its result to a static class field. Multiple static blocks per "
    "class are flagged."
)


@dataclass(frozen=True)
class StaticBlock:
    start: int
    end: int
    branched: bool
    ordinal: int


@dataclass(frozen=True)
class _OpenBlock:
    start: int
    depth: int
    branched: bool


def _param_name(token: str) -> str | None:
    stripped = token.strip()
    if not stripped or stripped.startswith(("{", "[", "...")):
        return None
    name_match = _PARAM_NAME_PATTERN.match(stripped)
    if not name_match or name_match.group(1) in _NON_PARAM_KEYWORDS:
        return None
    return name_match.group(1)


def _collect_param_names(text: str) -> set[str]:
    candidates = (
        _param_name(token)
        for masked in mask_lines(text)
        for m in PARAM_REASSIGN_FN_PATTERN.finditer(masked)
        for token in (m.group("params") or m.group("arrow_params") or "").split(",")
    )
    return {name for name in candidates if name is not None}


def _is_callable_header(masked: str) -> bool:
    return bool(
        "=>" in masked
        or _FUNCTION_HEADER_PATTERN.match(masked)
        or _CALL_HEADER_PATTERN.match(masked)
    )


def _param_write_pattern(params: set[str]) -> re.Pattern[str]:
    return re.compile(
        r"\b(?P<name>" + "|".join(re.escape(p) for p in params) + r")\b"
        r"(?:\s*=(?!=)|\s*\+=|\s*-=|\s*\*=|\s*/=|\s*%=|\s*\.[a-zA-Z_$][\w$]*\s*=(?!=)|\s*\[[^\]]+\]\s*=(?!=))"
    )


def detect_param_reassignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    params = _collect_param_names(text)
    if not params:
        return []
    pattern = _param_write_pattern(params)
    return [
        make_match(
            "param.reassign",
            lineno,
            m.start(),
            raw,
            _PARAM_REASSIGN_FIX,
            {"name": m.group("name") or ""},
        )
        for lineno, raw, masked in iter_masked_lines(text)
        if not looks_like_declaration(raw, masked) and not _is_callable_header(masked)
        for m in pattern.finditer(masked)
        if (m.group("name") or "") not in KNOWN_PROP_REASSIGN_PARAM_NAMES
    ]


def _declared_lets(text: str) -> list[tuple[int, str, str]]:
    declared = (
        (idx, raw, LET_DECL_PATTERN.match(masked))
        for idx, (raw, masked) in enumerate(
            zip(text.splitlines(), mask_lines(text)), start=1
        )
        if not LET_FOR_HEAD_PATTERN.search(masked)
    )
    return [
        (idx, raw, m.group("name")) for idx, raw, m in declared if m and m.group("name")
    ]


def _is_reassigned(body: str, raw: str, name: str) -> bool:
    reassign_pattern = re.compile(
        rf"\b{re.escape(name)}\b\s*(?:=(?!=)|\+=|-=|\*=|/=|%=|\+\+|--|\.[a-zA-Z_$][\w$]*\s*=(?!=)|\[[^\]]+\]\s*=(?!=))"
    )
    first_decl_idx = body.find(raw)
    scan_from = first_decl_idx + len(raw) if first_decl_idx >= 0 else 0
    return bool(reassign_pattern.search(body[scan_from:]))


def detect_let_could_be_const(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    declared = _declared_lets(text)
    if not declared:
        return []
    body = "\n".join(mask_lines(text))
    return [
        make_match("let.could-be-const", lineno, 0, raw, _LET_FIX, {"name": name})
        for lineno, raw, name in declared
        if not _is_reassigned(body, raw, name)
    ]


def _advance_block(block: _OpenBlock, masked: str) -> _OpenBlock:
    return _OpenBlock(
        start=block.start,
        depth=block.depth + masked.count("{") - masked.count("}"),
        branched=block.branched or bool(_BRANCH_KEYWORD_PATTERN.search(masked)),
    )


def static_blocks(text: str) -> list[StaticBlock]:
    closed: list[StaticBlock] = []
    open_block: _OpenBlock | None = None
    ordinal = 0
    for idx, masked in enumerate(mask_lines(text), start=1):
        if _CLASS_DECL_PATTERN.search(masked):
            ordinal = 0
        if open_block is None:
            if STATIC_BLOCK_OPEN_PATTERN.search(masked):
                ordinal += 1
                depth = masked.count("{") - masked.count("}")
                open_block = _OpenBlock(start=idx, depth=depth, branched=False)
            continue
        open_block = _advance_block(open_block, masked)
        if open_block.depth <= 0:
            closed.append(
                StaticBlock(open_block.start, idx, open_block.branched, ordinal)
            )
            open_block = None
    return closed


def canonical_static_block_line_ranges(text: str) -> list[tuple[int, int]]:
    return [
        (block.start, block.end)
        for block in static_blocks(text)
        if not block.branched and block.ordinal == 1
    ]


def filter_matches_in_canonical_static_blocks(
    matches: list[Match], text: str
) -> list[Match]:
    ranges = canonical_static_block_line_ranges(text)
    if not ranges:
        return matches
    return [
        m
        for m in matches
        if m.detector not in _CANONICAL_FILTERED_DETECTORS
        or not any(start <= m.line <= end for start, end in ranges)
    ]


def _static_block_match(block: StaticBlock, lines: list[str]) -> Match:
    excerpt = lines[block.start - 1] if block.start - 1 < len(lines) else ""
    reason = (
        "branching inside static block"
        if block.branched
        else "multiple static blocks per class"
    )
    return make_match(
        "static-block.mutation",
        block.start,
        0,
        excerpt,
        _STATIC_BLOCK_FIX,
        {"reason": reason},
    )


def detect_static_block_mutation(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    lines = text.splitlines()
    return [
        _static_block_match(block, lines)
        for block in static_blocks(text)
        if block.branched or block.ordinal > 1
    ]
