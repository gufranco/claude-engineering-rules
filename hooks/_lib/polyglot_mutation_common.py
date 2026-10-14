from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import Enum

from .guard_runner import Finding


class CommentStyle(Enum):
    C = "c"
    HASH = "hash"
    LUA = "lua"


@dataclass(frozen=True, slots=True)
class LineRule:
    pattern: re.Pattern[str]
    message: str
    blocking: bool = True
    unless: re.Pattern[str] | None = None


SUPPRESSION_DIRECTIVE = re.compile(
    r"NOLINT|//\s*nolint|rubocop:disable|@Suppress(?:Warnings)?\s*\(|#!?\[allow\(|"
    r"//\s*ignore(?:_for_file)?\s*:|swiftlint:disable|luacheck:\s*ignore|#\s*noqa|"
    r"shellcheck\s+disable|#pragma\s+warning\s+disable|tflint-ignore|checkov:skip"
)
QUOTES = ('"', "'", "`")
BLOCK_COMMENTS = {CommentStyle.C: ("/*", "*/"), CommentStyle.LUA: ("--[[", "]]")}
LINE_COMMENTS = {CommentStyle.C: "//", CommentStyle.LUA: "--", CommentStyle.HASH: "#"}


def _blank(segment: str) -> str:
    return "".join(ch if ch == "\n" else " " for ch in segment)


def _string_end(text: str, start: int) -> int:
    quote = text[start]
    index = start + 1
    while index < len(text) and text[index] not in (quote, "\n"):
        index += 2 if text[index] == "\\" else 1
    return index if index < len(text) and text[index] == quote else index - 1


def _comment_span(text: str, index: int, style: CommentStyle) -> int:
    block = BLOCK_COMMENTS.get(style)
    if block and text.startswith(block[0], index):
        close = text.find(block[1], index + len(block[0]))
        return len(text) if close < 0 else close + len(block[1])
    line = LINE_COMMENTS[style]
    if not text.startswith(line, index):
        return -1
    if style is CommentStyle.HASH and index > 0 and not text[index - 1].isspace():
        return -1
    newline = text.find("\n", index)
    return len(text) if newline < 0 else newline


def _mask_step(text: str, index: int, style: CommentStyle) -> tuple[str, int]:
    comment_end = _comment_span(text, index, style)
    if comment_end >= 0:
        return _blank(text[index:comment_end]), comment_end
    if text[index] in QUOTES:
        end = _string_end(text, index)
        inner = _blank(text[index + 1 : end])
        closing = text[end] if end > index and text[end] == text[index] else ""
        return text[index] + inner + closing, end + 1
    return text[index], index + 1


def mask_source(text: str, style: CommentStyle) -> list[str]:
    pieces: list[str] = []
    index = 0
    while index < len(text):
        piece, index = _mask_step(text, index, style)
        pieces.append(piece)
    return "".join(pieces).split("\n")[: len(text.splitlines()) or 1]


def is_suppressed(raw_lines: Sequence[str], index: int) -> bool:
    nearby = raw_lines[max(0, index - 1) : index + 1]
    return any(SUPPRESSION_DIRECTIVE.search(line) for line in nearby)


def _rule_hits(rule: LineRule, masked: Sequence[str]) -> Iterator[tuple[int, LineRule]]:
    for index, line in enumerate(masked):
        if rule.pattern.search(line) and not (rule.unless and rule.unless.search(line)):
            yield index, rule


def scan_rules(
    text: str, style: CommentStyle, rules: Sequence[LineRule]
) -> tuple[Finding, ...]:
    raw = text.splitlines()
    masked = mask_source(text, style)
    hits = sorted(hit for rule in rules for hit in _rule_hits(rule, masked))
    return tuple(
        Finding(line=index + 1, message=rule.message, blocking=rule.blocking)
        for index, rule in hits
        if not is_suppressed(raw, index)
    )


def _close_index(masked: Sequence[str], start: int) -> int:
    depth = 0
    for index in range(start, len(masked)):
        depth += masked[index].count("{") - masked[index].count("}")
        if depth <= 0 and "{" in "".join(masked[start : index + 1]):
            return index
    return len(masked) - 1


def body_line_ranges(
    masked: Sequence[str], header: re.Pattern[str]
) -> list[tuple[int, int]]:
    return [
        (index, _close_index(masked, index))
        for index, line in enumerate(masked)
        if header.search(line)
    ]


@dataclass(frozen=True, slots=True)
class NamedRule:
    pattern: re.Pattern[str]
    template: str
    blocking: bool = True
    unless: re.Pattern[str] | None = None


def scan_named(
    text: str, style: CommentStyle, rules: Sequence[NamedRule]
) -> tuple[Finding, ...]:
    raw = text.splitlines()
    masked = mask_source(text, style)
    found = [
        Finding(
            line=index + 1,
            message=rule.template.format(**match.groupdict()),
            blocking=rule.blocking,
        )
        for index, line in enumerate(masked)
        for rule in rules
        for match in [rule.pattern.search(line)]
        if match is not None and not (rule.unless and rule.unless.search(line))
    ]
    return tuple(hit for hit in found if not is_suppressed(raw, hit.line - 1))


def suppressed_filter(text: str, findings: Sequence[Finding]) -> tuple[Finding, ...]:
    raw = text.splitlines()
    return tuple(hit for hit in findings if not is_suppressed(raw, hit.line - 1))
