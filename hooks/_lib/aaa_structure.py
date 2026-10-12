from __future__ import annotations

import ast
import bisect
import io
import os
import re
import tokenize
import warnings
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from _lib.comment_families import C, JAVASCRIPT, SHELL, CommentFamily
from _lib.comment_regions import line_starts
from _lib.comment_syntax import (
    AAA_MARKERS,
    bare_marker,
    is_test_path,
    mask_code,
    scan_hits,
)

MARKER_WORD = re.compile(r"^(Arrange|Act|Assert)\b")
JS_CASE_START = re.compile(r"(?<![\w$.])(?:it|test)\b")
JS_IDENTIFIER = re.compile(r"[A-Za-z_$][\w$]*")
GO_CASE = re.compile(
    r"^func\s+(?P<name>Test\w*)\s*\(\s*\w+\s+\*testing\.T\s*\)[^{\n]*\{", re.M
)
BATS_CASE = re.compile(r"^[ \t]*@test\s+(?P<name>\S[^\n]*?)\s*\{[ \t]*$", re.M)
JS_EXTENSIONS = frozenset(
    {".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"}
)
QUOTES = "\"'`"
MAX_CALL_CHAIN = 8
SKIPPED_CHAIN_MEMBERS = frozenset({"todo"})


class CaseLanguage(StrEnum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    GO = "go"
    BATS = "bats"


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    header_line: int
    first_line: int
    last_line: int
    text: str


@dataclass(frozen=True, slots=True)
class Marker:
    line: int
    word: str
    bare: bool


@dataclass(frozen=True, slots=True)
class Violation:
    name: str
    line: int
    reason: str


def case_language(path: str) -> CaseLanguage | None:
    if not is_test_path(path):
        return None
    extension = os.path.splitext(path.lower())[1]
    if extension == ".py":
        return CaseLanguage.PYTHON
    if extension in JS_EXTENSIONS:
        return CaseLanguage.JAVASCRIPT
    if path.lower().endswith("_test.go"):
        return CaseLanguage.GO
    return CaseLanguage.BATS if extension == ".bats" else None


def _python_tokens(text: str) -> list[tokenize.TokenInfo]:
    try:
        return list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return []


def _header_end(
    tokens: list[tokenize.TokenInfo], rows: list[int], def_line: int
) -> int:
    depth = 0
    for token in tokens[bisect.bisect_left(rows, def_line) :]:
        if token.type != tokenize.OP:
            continue
        if token.string in "([{":
            depth += 1
        elif token.string in ")]}":
            depth -= 1
        elif token.string == ":" and depth == 0:
            return token.start[0]
    return def_line


def _python_cases(text: str) -> list[Case]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return []
    tokens = _python_tokens(text)
    rows = [token.start[0] for token in tokens]
    lines = text.split("\n")
    cases: list[Case] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test"):
            continue
        start = min([node.lineno] + [item.lineno for item in node.decorator_list]) - 1
        header = _header_end(tokens, rows, node.lineno)
        last = (node.end_lineno or node.lineno) - 1
        cases.append(
            Case(
                node.name,
                node.lineno - 1,
                header,
                last,
                "\n".join(lines[start : last + 1]),
            )
        )
    return sorted(cases, key=lambda case: case.header_line)


def _matching(text: str, opener_index: int, opener: str, closer: str) -> int:
    depth = 0
    for index in range(opener_index, len(text)):
        if text[index] == opener:
            depth += 1
        elif text[index] == closer:
            depth -= 1
            if depth == 0:
                return index
    return len(text) - 1


def _skip_spaces(text: str, cursor: int) -> int:
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    return cursor


def _test_call(masked: str, cursor: int) -> tuple[int, int] | None:
    for _ in range(MAX_CALL_CHAIN):
        cursor = _skip_spaces(masked, cursor)
        character = masked[cursor : cursor + 1]
        if character == ".":
            member = JS_IDENTIFIER.match(masked, _skip_spaces(masked, cursor + 1))
            if member is None or member.group(0) in SKIPPED_CHAIN_MEMBERS:
                return None
            cursor = member.end()
        elif character == "`":
            cursor = masked.find("`", cursor + 1) + 1
        elif character == "(":
            close = _matching(masked, cursor, "(", ")")
            if (
                masked[
                    _skip_spaces(masked, close + 1) : _skip_spaces(masked, close + 1)
                    + 1
                ]
                != "("
            ):
                return cursor, close
            cursor = close + 1
        else:
            return None
    return None


def _callback_brace(masked: str, start: int, close: int) -> int | None:
    depth = 0
    for index in range(start, close):
        character = masked[index]
        if character in "([":
            depth += 1
        elif character in ")]}":
            depth -= 1
        elif character == "{":
            previous = masked[:index].rstrip()[-1:]
            if depth == 0 and previous in (">", ")"):
                return index
            depth += 1
    return None


def _brace_case(
    masked: str, starts: list[int], header: int, opener: int | None
) -> tuple[int, int, int]:
    header_line = bisect.bisect_right(starts, header) - 1
    if opener is None:
        return header_line, header_line + 1, header_line
    closer = _matching(masked, opener, "{", "}")
    first = bisect.bisect_right(starts, opener)
    last = bisect.bisect_right(starts, closer) - 2
    return header_line, first, last


def _javascript_cases(text: str) -> list[Case]:
    masked = mask_code(text, JAVASCRIPT)
    starts = line_starts(text)
    cases: list[Case] = []
    for match in JS_CASE_START.finditer(masked):
        call = _test_call(masked, match.end())
        if call is None:
            continue
        open_paren, close_paren = call
        title = _skip_spaces(masked, open_paren + 1)
        if masked[title : title + 1] not in tuple(QUOTES):
            continue
        title_end = masked.find(masked[title], title + 1)
        brace = _callback_brace(masked, title_end + 1, close_paren)
        header, first, last = _brace_case(masked, starts, match.start(), brace)
        cases.append(
            Case(
                text[title + 1 : title_end],
                header,
                first,
                last,
                text[match.start() : close_paren + 1],
            )
        )
    return cases


def _pattern_cases(
    text: str, family: CommentFamily, pattern: re.Pattern[str]
) -> list[Case]:
    masked = mask_code(text, family)
    starts = line_starts(text)
    cases: list[Case] = []
    for match in pattern.finditer(masked):
        opener = match.start() + match.group(0).rindex("{")
        closer = _matching(masked, opener, "{", "}")
        header, first, last = _brace_case(masked, starts, match.start(), opener)
        name = text[match.start("name") : match.end("name")].strip("\"'")
        cases.append(Case(name, header, first, last, text[match.start() : closer + 1]))
    return cases


def find_cases(text: str, language: CaseLanguage) -> list[Case]:
    if language is CaseLanguage.PYTHON:
        return _python_cases(text)
    if language is CaseLanguage.JAVASCRIPT:
        return _javascript_cases(text)
    if language is CaseLanguage.GO:
        return _pattern_cases(text, C, GO_CASE)
    return _pattern_cases(text, SHELL, BATS_CASE)


def _python_markers(text: str) -> list[Marker]:
    lines = text.split("\n")
    markers: list[Marker] = []
    for token in _python_tokens(text):
        word = (
            MARKER_WORD.match(token.string[1:].strip())
            if token.type == tokenize.COMMENT
            else None
        )
        if word is None:
            continue
        row, column = token.start
        bare = (
            token.string == f"# {word.group(1)}" and not lines[row - 1][:column].strip()
        )
        markers.append(Marker(row - 1, word.group(1), bare))
    return markers


def markers_in(text: str, language: CaseLanguage) -> list[Marker]:
    if language is CaseLanguage.PYTHON:
        return _python_markers(text)
    lines = text.split("\n")
    family = {CaseLanguage.BATS: SHELL, CaseLanguage.GO: C}.get(language, JAVASCRIPT)
    markers: list[Marker] = []
    for line, hit in scan_hits(text, family).items():
        word = MARKER_WORD.match(hit.body or "")
        if word is not None:
            markers.append(
                Marker(
                    line, word.group(1), bare_marker(lines[line], hit) == word.group(1)
                )
            )
    return markers


def _sequence_problem(words: list[str]) -> str:
    missing = [word for word in AAA_MARKERS if word not in words]
    duplicated = [word for word in AAA_MARKERS if words.count(word) > 1]
    parts = []
    if missing:
        parts.append("missing " + ", ".join(missing))
    if duplicated:
        parts.append("duplicate " + ", ".join(duplicated))
    if parts:
        return "; ".join(parts)
    return f"markers out of order: got {', '.join(words)}; expected {', '.join(AAA_MARKERS)}"


def _layout_problems(case: Case, bare: list[Marker], lines: list[str]) -> list[str]:
    problems: list[str] = []
    first_code = next(
        (
            index
            for index in range(case.first_line, case.last_line + 1)
            if lines[index].strip()
        ),
        None,
    )
    if first_code != bare[0].line:
        problems.append("the body must open with the Arrange marker")
    for marker in bare[1:]:
        above = lines[marker.line - 1].strip(), lines[marker.line - 2].strip()
        if above[0] or not above[1]:
            problems.append(
                f"exactly one blank line must precede the {marker.word} marker"
            )
    for marker in bare:
        following = (
            lines[marker.line + 1].strip() if marker.line + 1 <= case.last_line else ""
        )
        if not following:
            problems.append(f"the {marker.word} block is empty")
    return problems


def case_problems(case: Case, markers: list[Marker], lines: list[str]) -> list[str]:
    inside = [
        marker for marker in markers if case.first_line <= marker.line <= case.last_line
    ]
    problems = [
        f"the {marker.word} marker on line {marker.line + 1} is not bare: "
        "write it alone on its line, nothing after the word"
        for marker in inside
        if not marker.bare
    ]
    words = [marker.word for marker in inside if marker.bare]
    if words != list(AAA_MARKERS):
        return [*problems, _sequence_problem(words)]
    return problems + _layout_problems(
        case, [marker for marker in inside if marker.bare], lines
    )


def changed_cases(before: str, after: str, language: CaseLanguage) -> list[Case]:
    remaining = Counter((case.name, case.text) for case in find_cases(before, language))
    changed: list[Case] = []
    for case in find_cases(after, language):
        key = (case.name, case.text)
        if remaining[key]:
            remaining[key] -= 1
            continue
        changed.append(case)
    return changed


def violations(path: str, before: str, after: str) -> list[Violation]:
    language = case_language(path)
    if language is None:
        return []
    cases = changed_cases(before, after, language)
    if not cases:
        return []
    markers = markers_in(after, language)
    lines = after.split("\n")
    found: list[Violation] = []
    for case in cases:
        problems = case_problems(case, markers, lines)
        if problems:
            found.append(
                Violation(case.name, case.header_line + 1, "; ".join(problems))
            )
    return found
