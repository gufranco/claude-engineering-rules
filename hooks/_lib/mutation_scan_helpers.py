from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .mutation_detectors_core import (
    Match,
    mask_lines,
    mask_text,
    strip_strings_comments,
    truncate_excerpt,
)

EXCERPT_LIMIT = 120
LOOKBACK_LINES = 61
ASSIGN_OP_ALTERNATION = (
    r"=(?!=)|\+=|-=|\*=|/=|%=|\*\*=|<<=|>>=|>>>=|&=|\|=|\^=|&&=|\|\|=|\?\?="
)

_DECLARATION_PREFIXES = (
    "const ",
    "let ",
    "var ",
    "export const ",
    "export let ",
    "export var ",
)
_MODIFIER_PREFIXES = ("public ", "private ", "protected ", "readonly ", "static ")
_TYPED_FIELD_PATTERN = re.compile(r"^\s*[a-zA-Z_$][\w$]*\s*[?!]?\s*:\s*[^=]+$")

ScannedLine = tuple[int, str, str]


def iter_stripped_lines(text: str) -> list[ScannedLine]:
    return [
        (idx, line, strip_strings_comments(line))
        for idx, line in enumerate(text.splitlines(), start=1)
        if line.strip()
    ]


def iter_masked_lines(text: str) -> list[ScannedLine]:
    return [
        (idx, line, masked)
        for idx, (line, masked) in enumerate(
            zip(text.splitlines(), mask_lines(text)), start=1
        )
        if line.strip()
    ]


def make_match(
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
        text=truncate_excerpt(raw, EXCERPT_LIMIT),
        detector=detector,
        fix_hint=fix_hint,
        metadata=metadata or {},
    )


def looks_like_declaration(line: str, masked: str) -> bool:
    stripped = masked.strip()
    if stripped.startswith(_DECLARATION_PREFIXES):
        return True
    if stripped.startswith(_MODIFIER_PREFIXES):
        return True
    return bool(_TYPED_FIELD_PATTERN.match(line))


def name_alternation(names: Iterable[str]) -> str:
    return "|".join(re.escape(name) for name in names)


def collect_names(pattern: re.Pattern[str], text: str) -> frozenset[str]:
    return frozenset(m.group("name") for m in pattern.finditer(text))


def masked_lookback(lines: list[str], lineno: int) -> str:
    start = max(0, lineno - LOOKBACK_LINES)
    between = "\n".join(lines[start:lineno])
    return mask_text(between) if between else ""


def is_inside_open_call(masked: str, opener: str) -> bool:
    idx = masked.rfind(opener)
    if idx < 0:
        return False
    scope = masked[idx:]
    return scope.count("(") > scope.count(")")


def _accept_every_match(_match: re.Match[str], _lineno: int) -> bool:
    return True


@dataclass(frozen=True)
class NamedWriteSpec:
    detector: str
    pattern: re.Pattern[str]
    skip_line: re.Pattern[str] | None
    fix_hint: str
    metadata: Callable[[re.Match[str]], dict[str, str]]
    accepts: Callable[[re.Match[str], int], bool] = _accept_every_match


def _line_is_scanned(spec: NamedWriteSpec, masked: str) -> bool:
    return spec.skip_line is None or not spec.skip_line.search(masked)


def scan_named_writes(text: str, spec: NamedWriteSpec) -> list[Match]:
    return [
        make_match(
            spec.detector, lineno, m.start("name"), raw, spec.fix_hint, spec.metadata(m)
        )
        for lineno, raw, masked in iter_masked_lines(text)
        if _line_is_scanned(spec, masked)
        for m in spec.pattern.finditer(masked)
        if spec.accepts(m, lineno)
    ]
