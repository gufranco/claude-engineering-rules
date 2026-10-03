"""Split a Bash command string into the commands it would actually run.

Quotes are respected, heredoc bodies are dropped as data, and every line is
split at unquoted `;`, `&` and `|` operators. A line whose quoting does not
balance yields nothing, so a fragment of a string is never mistaken for a
command.
"""

from __future__ import annotations

import os
import re
import shlex

OPERATOR_CHARS = ";&|"
HEREDOC_START = re.compile(r"(?<!<)<<(?!<)-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")
QUOTED_HEREDOC_START = re.compile(
    r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1"
)


def strip_heredoc_bodies(command: str) -> str:
    """Drop the body lines of every heredoc, which are data, never commands."""
    kept: list[str] = []
    delimiter = ""
    for line in command.splitlines():
        if delimiter:
            if line.strip() == delimiter:
                delimiter = ""
            continue
        kept = [*kept, line]
        match = HEREDOC_START.search(line)
        if match:
            delimiter = match.group(1)
    return "\n".join(kept)


def line_segments(line: str) -> list[list[str]]:
    """Split one line into commands at unquoted ; & | operators."""
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
    """Every command in `command`, tokenized, in execution order."""
    lines = strip_heredoc_bodies(command).splitlines()
    return [segment for line in lines for segment in line_segments(line)]


def _mask_line(line: str, state: str) -> tuple[str, str]:
    """Blank single-quoted text on one line; `state` is the open quote."""
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
    """Blank text the shell never executes, keeping offsets and line breaks.

    Single-quoted strings and the bodies of heredocs with a quoted delimiter
    are literal; double-quoted strings and unquoted heredocs still run `$(...)`
    and are kept.
    """
    out: list[str] = []
    state = ""
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
        match = QUOTED_HEREDOC_START.search(line) if state == "" else None
        if match:
            delimiter, literal_body = match.group(2), bool(match.group(1))
    return "\n".join(out)


def command_head(tokens: list[str]) -> tuple[str, list[str]]:
    """Return the base command name and its tokens, past env and `command`."""
    i = 0
    while i < len(tokens) and "=" in tokens[i] and not tokens[i].startswith("-"):
        i += 1
    if i >= len(tokens):
        return "", []
    if tokens[i] == "command" and i + 1 < len(tokens):
        i += 1
    return os.path.basename(tokens[i]), tokens[i:]
