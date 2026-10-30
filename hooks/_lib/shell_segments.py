from __future__ import annotations

import os
import re
import shlex

OPERATOR_CHARS = ";&|"
DATA_SINKS = frozenset({"cat", "tee", "git", "gh", "glab"})
CODE_INTERPRETERS = frozenset({"python", "python3", "node", "ruby", "perl"})
HEREDOC_START = re.compile(r"(?<!<)<<(?!<)-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")
QUOTED_HEREDOC_START = re.compile(
    r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1"
)


def strip_heredoc_bodies(command: str) -> str:
    kept: list[str] = []
    pending: tuple[str, ...] = ()
    state = ""
    for line in command.splitlines():
        if pending:
            pending = pending[1:] if line.strip() == pending[0] else pending
            continue
        kept = [*kept, line]
        matches, state = _unquoted_matches(HEREDOC_START, line, state)
        pending = tuple(match.group(1) for match in matches)
    return "\n".join(kept)


def strip_data_heredoc_bodies(command: str, sinks: frozenset[str] = DATA_SINKS) -> str:
    kept: list[str] = []
    delimiter = ""
    state = ""
    drop = False
    for line in command.splitlines():
        if delimiter and line.strip() == delimiter:
            delimiter = ""
        elif delimiter and drop:
            continue
        elif not delimiter:
            match, state = _unquoted_match(HEREDOC_START, line, state)
            delimiter = match.group(1) if match else ""
            drop = match is not None and _feeds_data_sink(line, match, sinks)
        kept = [*kept, line]
    return "\n".join(kept)


CONTAINER_RM_FLAG = re.compile(r"(?<!\S)--rm(?==|\s|$)")


def mask_container_rm_flag(command: str) -> str:
    return CONTAINER_RM_FLAG.sub("--auto-remove", command)


def _feeds_data_sink(line: str, match: re.Match[str], sinks: frozenset[str]) -> bool:
    if "|" in line[match.end() :]:
        return False
    segments = line_segments(line[: match.start()])
    return bool(segments) and command_head(segments[-1])[0] in sinks


UNQUOTED_OPERATOR = re.compile(r"&&|\|\||[;|&\n]")
STATEMENT_OPERATOR = re.compile(r"&&|\|\||\|&|(?<![<>&])&(?![>&])|[;|\n]")


def unquoted_segments(command: str) -> list[str]:
    blanked_text = _blank_command(command)
    bounds = [(m.start(), m.end()) for m in UNQUOTED_OPERATOR.finditer(blanked_text)]
    starts = [0, *(end for _, end in bounds)]
    ends = [*(start for start, _ in bounds), len(command)]
    return [command[a:b] for a, b in zip(starts, ends) if command[a:b].strip()]


def operator_segments(command: str) -> list[tuple[str, str]]:
    matches = list(STATEMENT_OPERATOR.finditer(_blank_command(command)))
    starts = [0, *(m.end() for m in matches)]
    ends = [*(m.start() for m in matches), len(command)]
    leading = ["", *(m.group() for m in matches)]
    return [
        (command[a:b], operator)
        for a, b, operator in zip(starts, ends, leading)
        if command[a:b].strip()
    ]


def _blank_command(command: str) -> str:
    parts: list[str] = []
    state = ""
    delimiter = ""
    for index, line in enumerate(command.split("\n")):
        separator = [" " if state or delimiter else "\n"] if index else []
        if delimiter:
            blanked = " " * len(line)
            delimiter = "" if line.strip() == delimiter else delimiter
        else:
            match, _ = _unquoted_match(HEREDOC_START, line, state)
            blanked, state = _blank_quoted(line, state)
            delimiter = match.group(1) if match else ""
        parts = [*parts, *separator, blanked]
    return "".join(parts)


def _blank_quoted(line: str, state: str) -> tuple[str, str]:
    out: list[str] = []
    escaped = False
    for char in line:
        literal = bool(state) and not (char == state and not escaped)
        out = [*out, " " if literal else char]
        if escaped:
            escaped = False
        elif char == "\\" and state != "'":
            escaped = True
        elif state and char == state:
            state = ""
        elif not state and char in "'\"":
            state = char
    return "".join(out), state


def _unquoted_matches(
    pattern: re.Pattern[str], line: str, state: str
) -> tuple[list[re.Match[str]], str]:
    blanked, next_state = _blank_quoted(line, state)
    return [m for m in pattern.finditer(line) if blanked[m.start()] == "<"], next_state


def _unquoted_match(
    pattern: re.Pattern[str], line: str, state: str
) -> tuple[re.Match[str] | None, str]:
    matches, next_state = _unquoted_matches(pattern, line, state)
    return (matches[0] if matches else None), next_state


def line_segments(line: str) -> list[list[str]]:
    lexer = shlex.shlex(line, posix=True, punctuation_chars=OPERATOR_CHARS)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return []
    segments: list[list[str]] = [[]]
    for token in tokens:
        if set(token) <= set(OPERATOR_CHARS):
            segments = [*segments, []]
        else:
            segments = [*segments[:-1], [*segments[-1], token]]
    return [segment for segment in segments if segment]


def quoted_segments(command: str) -> list[list[str]]:
    lines = strip_heredoc_bodies(command).splitlines()
    return [segment for line in lines for segment in line_segments(line)]


def _mask_line(line: str, state: str) -> tuple[str, str]:
    out: list[str] = []
    escaped = False
    for char in line:
        if state == "'":
            closing = char == "'"
            out = [*out, char if closing else " "]
            state = "" if closing else state
            continue
        out = [*out, char]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            state = "" if state == '"' else '"'
        elif char == "'" and state == "":
            state = "'"
    return "".join(out), state


def mask_literal_text(command: str) -> str:
    out: list[str] = []
    state = ""
    quote = ""
    delimiter = ""
    literal_body = False
    for line in command.split("\n"):
        if delimiter:
            done = line.strip() == delimiter
            out = [*out, "" if literal_body and not done else line]
            delimiter = "" if done else delimiter
            continue
        masked, state = _mask_line(line, state)
        out = [*out, masked]
        match, quote = _unquoted_match(QUOTED_HEREDOC_START, line, quote)
        if match:
            delimiter, literal_body = match.group(2), bool(match.group(1))
    return "\n".join(out)


def command_head(tokens: list[str]) -> tuple[str, list[str]]:
    i = 0
    while i < len(tokens) and "=" in tokens[i] and not tokens[i].startswith("-"):
        i += 1
    if i >= len(tokens):
        return "", []
    if tokens[i] == "command" and i + 1 < len(tokens):
        i += 1
    return os.path.basename(tokens[i]), tokens[i:]
