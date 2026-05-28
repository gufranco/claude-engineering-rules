"""Shared infrastructure for mutation-method-blocker detectors.

Holds the `Match` dataclass, payload-masking helpers, multi-line window
slicing, language detection, and the optional `ast-grep` escalation layer.
Detector modules import from here so the regex floor and AST ceiling stay
consistent across categories.

Public API:

    Match                                     - hit dataclass
    detect_lang(file_path) -> str | None      - tsx/ts/jsx/js or None
    supports_ast(lang) -> bool                - JS/TS family check
    strip_strings_comments(line) -> str       - mask quoted spans + comments
    window_around(lines, lineno, before=2, after=2) -> str
    ast_grep_path() -> str | None             - cached `which ast-grep`
    run_ast_grep(pattern, source, lang) -> list[Match]
    truncate_excerpt(line, limit=120) -> str

Design notes:

  - Regex floor first: every detector ships with a regex that handles the
    common case. AST escalation is optional and runs only when ast-grep is
    on PATH and `MUTATION_METHOD_AST=0` is not set.
  - Mask before match: comments and strings hide false-positive payloads
    like `"arr.push(item) is forbidden"` inside a string literal.
  - Fail open: any AST or subprocess error degrades to regex floor without
    blocking the user.
"""

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

_AST_GREP_PATH: str | None = None
_AST_GREP_RESOLVED: bool = False


@dataclass(frozen=True)
class Match:
    """A single detector hit."""

    line: int
    col: int
    text: str
    detector: str
    node_type: str = ""
    fix_hint: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


def detect_lang(file_path: str) -> str | None:
    """Return the ast-grep language tag for a JS/TS file extension."""
    if not file_path:
        return None
    lower = file_path.lower()
    for ext, lang in EXT_TO_LANG.items():
        if lower.endswith(ext):
            return lang
    return None


def supports_ast(lang: str | None) -> bool:
    """True only for JS/TS family languages."""
    return lang is not None and lang in AST_SUPPORTED_LANGS


def strip_strings_comments(line: str) -> str:
    """Mask string literals and line comments with whitespace.

    Preserves length and column positions so any column-based offset
    computed against the masked line still maps to the original line.
    Single-quoted, double-quoted, and backtick-quoted spans are replaced
    with spaces. Inline `//` comments and block comment openers are masked
    starting at the comment marker.
    """
    if not line:
        return line
    out: list[str] = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "/" and i + 1 < n and line[i + 1] == "/":
            out.append(" " * (n - i))
            break
        if ch == "/" and i + 1 < n and line[i + 1] == "*":
            j = i + 2
            while j < n - 1 and not (line[j] == "*" and line[j + 1] == "/"):
                j += 1
            if j < n - 1:
                out.append(" " * (j - i + 2))
                i = j + 2
                continue
            out.append(" " * (n - i))
            break
        if ch in ("'", '"', "`"):
            quote = ch
            j = i + 1
            while j < n and line[j] != quote:
                if line[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if quote == "`" and line[j] == "$" and j + 1 < n and line[j + 1] == "{":
                    depth = 1
                    j += 2
                    while j < n and depth > 0:
                        if line[j] == "{":
                            depth += 1
                        elif line[j] == "}":
                            depth -= 1
                        j += 1
                    continue
                j += 1
            span = j - i + 1 if j < n else n - i
            out.append(quote + " " * max(0, span - 2) + (quote if j < n else ""))
            i = i + span
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def window_around(
    lines: list[str], lineno: int, before: int = 2, after: int = 2
) -> str:
    """Return a multi-line slice centered on `lineno` (1-based).

    Used by detectors that need surrounding context to disambiguate scope
    membership: param reassignment walks up to the enclosing function;
    state-management allowance walks up to the enclosing `produce` or
    `createSlice` callsite.
    """
    if not lines:
        return ""
    idx = max(0, lineno - 1)
    start = max(0, idx - before)
    end = min(len(lines), idx + after + 1)
    return "\n".join(lines[start:end])


def ast_grep_path() -> str | None:
    """Return the cached ast-grep binary path or None when unavailable.

    Resolves once per process. Honors the `MUTATION_METHOD_AST=0` env var
    as an explicit opt-out so users can force regex-only mode for parity
    testing or troubleshooting.
    """
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


def run_ast_grep(pattern: str, source: str, lang: str) -> list[Match]:
    """Execute `ast-grep --pattern <p> --lang <lang> --json` over stdin.

    Returns an empty list on any error. The detector relying on the result
    falls back to its regex floor automatically.
    """
    binary = ast_grep_path()
    if not binary or not source or not pattern or lang not in AST_SUPPORTED_LANGS:
        return []
    try:
        proc = subprocess.run(
            [binary, "run", "--pattern", pattern, "--lang", lang, "--json=stream", "-"],
            input=source,
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return []
    if proc.returncode not in (0, 1):
        return []
    matches: list[Match] = []
    for raw in proc.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        rng = obj.get("range") or {}
        start = rng.get("start") or {}
        line = int(start.get("line", 0)) + 1
        col = int(start.get("column", 0)) + 1
        text = (obj.get("text") or "").strip()
        node_type = obj.get("kind") or ""
        matches.append(
            Match(
                line=line, col=col, text=text[:200], detector="ast", node_type=node_type
            )
        )
    return matches


def truncate_excerpt(line: str, limit: int = 120) -> str:
    """Trim a line for inclusion in error output."""
    stripped = line.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit].rstrip() + "..."
