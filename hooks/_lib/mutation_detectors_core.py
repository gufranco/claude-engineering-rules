from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field

EXT_TO_LANG: dict[str, str] = {
    ".tsx": "tsx",
    ".ts": "ts",
    ".jsx": "jsx",
    ".js": "js",
    ".mjs": "js",
    ".cjs": "js",
    ".mts": "ts",
    ".cts": "ts",
}

AST_SUPPORTED_LANGS: frozenset[str] = frozenset({"js", "jsx", "ts", "tsx"})
AST_GREP_TIMEOUT_S = 2.0
AST_GREP_TEXT_LIMIT = 200

_AST_GREP_PATH: str | None = None
_AST_GREP_RESOLVED: bool = False


@dataclass(frozen=True)
class Match:
    line: int
    col: int
    text: str
    detector: str
    node_type: str = ""
    fix_hint: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


def detect_lang(file_path: str) -> str | None:
    if not file_path:
        return None
    lower = file_path.lower()
    for ext, lang in EXT_TO_LANG.items():
        if lower.endswith(ext):
            return lang
    return None


def supports_ast(lang: str | None) -> bool:
    return lang is not None and lang in AST_SUPPORTED_LANGS


def _skip_interpolation(line: str, j: int) -> int:
    n = len(line)
    depth = 1
    while j < n and depth > 0:
        if line[j] == "{":
            depth += 1
        elif line[j] == "}":
            depth -= 1
        j += 1
    return j


def _quoted_scan_end(line: str, j: int, quote: str) -> int:
    n = len(line)
    while j < n and line[j] != quote:
        if line[j] == "\\" and j + 1 < n:
            j += 2
        elif quote == "`" and line.startswith("${", j):
            j = _skip_interpolation(line, j + 2)
        else:
            j += 1
    return j


def _strip_quoted(line: str, i: int) -> tuple[str, int]:
    n = len(line)
    quote = line[i]
    j = _quoted_scan_end(line, i + 1, quote)
    span = j - i + 1 if j < n else n - i
    return quote + " " * max(0, span - 2) + (quote if j < n else ""), i + span


def _strip_block_comment(line: str, i: int) -> tuple[str, int]:
    n = len(line)
    j = i + 2
    while j < n - 1 and not (line[j] == "*" and line[j + 1] == "/"):
        j += 1
    if j < n - 1:
        return " " * (j - i + 2), j + 2
    return " " * (n - i), n


def _strip_step(line: str, i: int) -> tuple[str, int]:
    if line.startswith("//", i):
        return " " * (len(line) - i), len(line)
    if line.startswith("/*", i):
        return _strip_block_comment(line, i)
    if line[i] in ("'", '"', "`"):
        return _strip_quoted(line, i)
    return line[i], i + 1


def strip_strings_comments(line: str) -> str:
    if not line:
        return line
    pieces: list[str] = []
    i = 0
    while i < len(line):
        piece, i = _strip_step(line, i)
        pieces.append(piece)
    return "".join(pieces)


LINE_BREAKS = frozenset("\n\r\v\f\x1c\x1d\x1e\x85  ")


def _blank(text: str, start: int, end: int) -> str:
    return "".join(ch if ch in LINE_BREAKS else " " for ch in text[start:end])


def _template_end(text: str, start: int) -> int:
    n = len(text)
    j = start
    while j < n and text[j] != "`":
        if text[j] == "\\" and j + 1 < n:
            j += 2
            continue
        if text[j] == "$" and j + 1 < n and text[j + 1] == "{":
            depth = 1
            j += 2
            while j < n and depth > 0:
                depth += {"{": 1, "}": -1}.get(text[j], 0)
                j += 1
            continue
        j += 1
    return j


def _quoted_end(text: str, start: int, quote: str) -> int:
    n = len(text)
    j = start
    while j < n and text[j] != quote and text[j] not in LINE_BREAKS:
        j += 2 if text[j] == "\\" and j + 1 < n else 1
    return j


def _masked_span(text: str, i: int) -> tuple[str, int] | None:
    n = len(text)
    pair = text[i : i + 2]
    if pair == "//":
        end = i
        while end < n and text[end] not in LINE_BREAKS:
            end += 1
        return " " * (end - i), end
    if pair == "/*":
        close = text.find("*/", i + 2)
        end = n if close < 0 else close + 2
        return _blank(text, i, end), end
    quote = text[i]
    if quote not in ("'", '"', "`"):
        return None
    j = _template_end(text, i + 1) if quote == "`" else _quoted_end(text, i + 1, quote)
    if j < n and text[j] == quote:
        return quote + _blank(text, i + 1, j) + quote, j + 1
    return quote + _blank(text, i + 1, j), j


def mask_lines(text: str) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(text):
        span = _masked_span(text, i)
        if span is None:
            out.append(text[i])
            i += 1
            continue
        masked, i = span
        out.append(masked)
    return "".join(out).splitlines()


def mask_text(text: str) -> str:
    return "\n".join(mask_lines(text))


def window_around(
    lines: list[str], lineno: int, before: int = 2, after: int = 2
) -> str:
    if not lines:
        return ""
    idx = max(0, lineno - 1)
    start = max(0, idx - before)
    end = min(len(lines), idx + after + 1)
    return "\n".join(lines[start:end])


def ast_grep_path() -> str | None:
    global _AST_GREP_PATH, _AST_GREP_RESOLVED
    if _AST_GREP_RESOLVED:
        return _AST_GREP_PATH
    _AST_GREP_RESOLVED = True
    if os.environ.get("MUTATION_METHOD_AST") == "0":
        _AST_GREP_PATH = None
        return None
    found = shutil.which("ast-grep") or shutil.which("sg")
    _AST_GREP_PATH = found
    return found


def _invoke_ast_grep(binary: str, pattern: str, source: str, lang: str) -> str | None:
    try:
        proc = subprocess.run(
            [binary, "run", "--pattern", pattern, "--lang", lang, "--json=stream", "-"],
            input=source,
            capture_output=True,
            text=True,
            timeout=AST_GREP_TIMEOUT_S,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None
    if proc.returncode not in (0, 1):
        return None
    return proc.stdout


def _parse_ast_grep_line(raw: str) -> Match | None:
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    start = (obj.get("range") or {}).get("start") or {}
    text = (obj.get("text") or "").strip()
    return Match(
        line=int(start.get("line", 0)) + 1,
        col=int(start.get("column", 0)) + 1,
        text=text[:AST_GREP_TEXT_LIMIT],
        detector="ast",
        node_type=obj.get("kind") or "",
    )


def run_ast_grep(pattern: str, source: str, lang: str) -> list[Match]:
    binary = ast_grep_path()
    if not binary or not source or not pattern or lang not in AST_SUPPORTED_LANGS:
        return []
    stdout = _invoke_ast_grep(binary, pattern, source, lang)
    if stdout is None:
        return []
    parsed = (_parse_ast_grep_line(raw.strip()) for raw in stdout.splitlines())
    return [match for match in parsed if match is not None]


def truncate_excerpt(line: str, limit: int = 120) -> str:
    stripped = line.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit].rstrip() + "..."
