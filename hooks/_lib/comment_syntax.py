from __future__ import annotations

import ast
import bisect
import functools
import re
import warnings
from collections import Counter
from dataclasses import dataclass

from _lib.comment_families import Boundary, CommentFamily, LineToken, StringToken
from _lib.comment_regions import TextRange, blank, line_starts, views
from _lib.comment_resolution import (
    DocumentView,
    document_view,
    is_test_path,
    notebook_code,
    resolve_family,
)
from _lib.tool_directive import TOOL_DIRECTIVE

MAX_INTERPOLATION_DEPTH = 8
EXPRESSION_LOOKBACK = 200
EXPRESSION_PRECEDERS = "(,=:[!&|?{};+-*%~^"
EXPRESSION_KEYWORDS = frozenset(
    {
        "return",
        "typeof",
        "case",
        "in",
        "of",
        "delete",
        "void",
        "throw",
        "new",
        "yield",
        "await",
    }
)
BRACKET_CLOSERS = {"{": "}", "(": ")"}
NESTED_QUOTES = "\"'`"

__all__ = [
    "AAA_MARKERS",
    "CommentFamily",
    "CommentHit",
    "DocumentView",
    "added_comment_lines",
    "bare_marker",
    "comment_lines",
    "document_view",
    "is_test_path",
    "mask_code",
    "notebook_code",
    "resolve_family",
    "scan_hits",
    "spans",
]

AAA_MARKERS: tuple[str, ...] = ("Arrange", "Act", "Assert")


@dataclass(frozen=True, slots=True)
class CommentHit:
    body: str | None
    token: str
    whole_line: bool


@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int
    comment: bool
    token: str
    inner_start: int
    inner_end: int


@functools.lru_cache(maxsize=128)
def _opener_pattern(family: CommentFamily) -> re.Pattern[str]:
    openers = (
        [block.open for block in family.blocks]
        + [line.token for line in family.lines]
        + [string.open for string in family.strings]
    )
    return re.compile("|".join(re.escape(opener) for opener in openers) or "(?!)")


def _boundary_ok(text: str, position: int, boundary: Boundary) -> bool:
    line_start = text.rfind("\n", 0, position) + 1
    previous = text[position - 1] if position > line_start else ""
    spaced = previous == "" or previous.isspace()
    if boundary is Boundary.SPACED:
        return spaced
    if boundary is Boundary.SHELL:
        return spaced or previous in ";|&()"
    if boundary is Boundary.FLOW:
        return spaced or previous in "[{,"
    if boundary is Boundary.OPERAND:
        return spaced or previous in "#(,=[{;:"
    if boundary is Boundary.LINE_START:
        return not text[line_start:position].strip()
    if boundary is Boundary.COLUMN0:
        return position == line_start
    if boundary is Boundary.EXPRESSION:
        return _expects_expression(text, position)
    return True


def _expects_expression(text: str, position: int) -> bool:
    cursor = position - 1
    floor = max(0, position - EXPRESSION_LOOKBACK)
    while cursor >= floor and text[cursor].isspace():
        cursor -= 1
    if cursor < floor:
        return True
    if text[cursor] in EXPRESSION_PRECEDERS:
        return True
    end = cursor + 1
    while cursor >= floor and (text[cursor].isalnum() or text[cursor] in "_$"):
        cursor -= 1
    return text[cursor + 1 : end] in EXPRESSION_KEYWORDS


def _line_token_ok(text: str, position: int, line: LineToken) -> bool:
    previous = text[position - 1] if position else ""
    if previous and previous in line.rejected_before:
        return False
    cursor = position + len(line.token)
    while cursor < len(text) and text[cursor] == line.token[-1]:
        cursor += 1
    following = text[cursor : cursor + 1]
    if following and following.lower() in line.rejected_after.lower():
        return False
    if line.requires_body and not _rest_of_line(text, cursor).strip():
        return False
    return _boundary_ok(text, position, line.boundary)


def _rest_of_line(text: str, cursor: int) -> str:
    newline = text.find("\n", cursor)
    return text[cursor : newline if newline != -1 else len(text)]


def _block_end(text: str, position: int, opener: str, closer: str, nests: bool) -> int:
    cursor = position + len(opener)
    depth = 1
    while depth and cursor < len(text):
        next_close = text.find(closer, cursor)
        if next_close == -1:
            return len(text)
        next_open = text.find(opener, cursor) if nests else -1
        if next_open != -1 and next_open < next_close:
            depth += 1
            cursor = next_open + len(opener)
            continue
        depth -= 1
        cursor = next_close + len(closer)
    return min(cursor, len(text))


def _regex_class_end(text: str, cursor: int) -> int:
    cursor += 1
    while cursor < len(text) and text[cursor] not in "]\n":
        cursor += 2 if text[cursor] == "\\" else 1
    return cursor + 1 if cursor < len(text) and text[cursor] == "]" else cursor


def _interpolation_at(text: str, cursor: int, string: StringToken, depth: int) -> str:
    if depth >= MAX_INTERPOLATION_DEPTH:
        return ""
    return next(
        (opener for opener in string.interpolations if text.startswith(opener, cursor)),
        "",
    )


def _interpolation_end(
    text: str, cursor: int, bracket: str, string: StringToken, depth: int
) -> int:
    closer = BRACKET_CLOSERS[bracket]
    level = 1
    while cursor < len(text):
        character = text[cursor]
        if character in NESTED_QUOTES:
            nested = (
                string
                if character == string.open
                else StringToken(character, character)
            )
            cursor = _string_end(text, cursor, nested, depth)
            continue
        if character == bracket:
            level += 1
        elif character == closer:
            level -= 1
            if level == 0:
                return cursor + 1
        cursor += 1
    return len(text)


def _string_end(text: str, position: int, string: StringToken, depth: int = 0) -> int:
    cursor = position + len(string.open)
    while cursor < len(text):
        character = text[cursor]
        if string.escape and character == string.escape:
            cursor += 2
            continue
        if string.line_terminated and character == "\n":
            return cursor
        if string.regex and character == "[":
            cursor = _regex_class_end(text, cursor)
            continue
        opener = _interpolation_at(text, cursor, string, depth)
        if opener:
            cursor = _interpolation_end(
                text, cursor + len(opener), opener[-1], string, depth + 1
            )
            continue
        if not text.startswith(string.close, cursor):
            cursor += 1
            continue
        if string.doubled and text.startswith(string.close, cursor + len(string.close)):
            cursor += 2 * len(string.close)
            continue
        return cursor + len(string.close)
    return len(text)


def _closed_inner_end(text: str, end: int, opener_end: int, closer: str) -> int:
    closer_start = end - len(closer)
    if closer_start >= opener_end and text.startswith(closer, closer_start):
        return closer_start
    return end


def _span_at(text: str, position: int, family: CommentFamily) -> Span | None:
    for block in family.blocks:
        if text.startswith(block.open, position) and (
            not block.column0 or _boundary_ok(text, position, Boundary.COLUMN0)
        ):
            end = _block_end(text, position, block.open, block.close, block.nests)
            inner = position + len(block.open)
            closed = _closed_inner_end(text, end, inner, block.close)
            return Span(position, end, True, block.open, inner, closed)
    for line in family.lines:
        if text.startswith(line.token, position) and _line_token_ok(
            text, position, line
        ):
            newline = text.find("\n", position)
            end = newline if newline != -1 else len(text)
            return Span(
                position, end, True, line.token, position + len(line.token), end
            )
    for string in family.strings:
        if text.startswith(string.open, position) and _boundary_ok(
            text, position, string.boundary
        ):
            end = _string_end(text, position, string)
            inner = position + len(string.open)
            closed = _closed_inner_end(text, end, inner, string.close)
            return Span(position, end, False, string.open, inner, closed)
    return None


def _first_scannable(text: str, family: CommentFamily) -> int:
    if not (family.shebang and text.startswith("#!")):
        return 0
    newline = text.find("\n")
    return newline if newline != -1 else len(text)


def spans(text: str, family: CommentFamily) -> list[Span]:
    found: list[Span] = []
    pattern = _opener_pattern(family)
    position = _first_scannable(text, family)
    while position < len(text):
        candidate = pattern.search(text, position)
        if candidate is None:
            break
        span = _span_at(text, candidate.start(), family)
        if span is None:
            position = candidate.start() + 1
            continue
        found.append(span)
        position = max(span.end, candidate.start() + 1)
    return found


def _comment_body(text: str, span: Span) -> str:
    newline = text.find("\n", span.inner_start)
    line_end = newline if newline != -1 else len(text)
    return (
        text[span.inner_start : min(line_end, span.inner_end)]
        .strip()
        .lstrip("*")
        .strip()
    )


def _hits_from_spans(text: str, found: list[Span]) -> dict[int, CommentHit]:
    starts = line_starts(text)
    hits: dict[int, CommentHit] = {}
    for span in (span for span in found if span.comment):
        first = bisect.bisect_right(starts, span.start) - 1
        last = bisect.bisect_right(starts, max(span.start, span.end - 1)) - 1
        whole_line = not text[starts[first] : span.start].strip()
        hits.setdefault(
            first, CommentHit(_comment_body(text, span), span.token, whole_line)
        )
        for line in range(first + 1, last + 1):
            hits.setdefault(line, CommentHit(None, "", False))
    return hits


def scan_hits(text: str, family: CommentFamily) -> dict[int, CommentHit]:
    merged: dict[int, CommentHit] = {}
    for view in views(text, family):
        for line, hit in _hits_from_spans(
            view.text, spans(view.text, view.family)
        ).items():
            merged.setdefault(line, hit)
    return dict(sorted(merged.items()))


def mask_code(text: str, family: CommentFamily) -> str:
    ranges: list[TextRange] = []
    for view in views(text, family):
        ranges.extend(view.premasked)
        ranges.extend(
            (span.start, span.end)
            if span.comment
            else (span.inner_start, span.inner_end)
            for span in spans(view.text, view.family)
        )
    return blank(text, ranges)


def bare_marker(line: str, hit: CommentHit) -> str | None:
    if not (hit.whole_line and hit.token):
        return None
    stripped = line.strip()
    return next(
        (word for word in AAA_MARKERS if stripped == f"{hit.token} {word}"), None
    )


def _reportable(hit: CommentHit, line: str, allow_aaa: bool) -> bool:
    if hit.body and TOOL_DIRECTIVE.match(hit.body):
        return False
    return not (allow_aaa and bare_marker(line, hit) is not None)


def _docstring_lines(text: str) -> list[int]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return []
    owners = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    return [
        node.body[0].lineno - 1
        for node in ast.walk(tree)
        if isinstance(node, owners)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ]


def _doc_lines(text: str, family: CommentFamily) -> list[int]:
    if family.docstrings:
        return _docstring_lines(text)
    if not family.doc_attribute:
        return []
    masked = mask_code(text, family)
    starts = line_starts(masked)
    return [
        bisect.bisect_right(starts, match.start()) - 1
        for match in re.finditer(family.doc_attribute, masked, re.M)
    ]


def comment_lines(
    text: str, family: CommentFamily, allow_aaa: bool = False
) -> list[tuple[int, str]]:
    source = text.split("\n")
    reported = {
        index: source[index].strip()
        for index, hit in scan_hits(text, family).items()
        if index < len(source) and _reportable(hit, source[index], allow_aaa)
    }
    for index in _doc_lines(text, family):
        reported.setdefault(index, source[index].strip())
    return sorted(reported.items())


def added_comment_lines(
    before: str, after: str, family: CommentFamily, allow_aaa: bool = False
) -> list[tuple[int, str]]:
    remaining = Counter(line for _, line in comment_lines(before, family, allow_aaa))
    added: list[tuple[int, str]] = []
    for index, line in comment_lines(after, family, allow_aaa):
        if remaining[line]:
            remaining[line] -= 1
            continue
        added.append((index, line))
    return added
