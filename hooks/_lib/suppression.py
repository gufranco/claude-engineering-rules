"""Shared suppression helper for ~/.claude hooks.
Centralizes the suppression-scan logic that was duplicated in
`as-any-blocker.py`, `console-log-blocker.py`, and `mutation-method-blocker.py`.

Only directives belonging to third-party tools are honored. A directive is a
comment another tool parses and acts on, which is the one comment form
`rules/code-style.md` exempts from the project-wide ban. This module never
recognizes an allow marker of our own invention: to silence one of these
hooks, use its `<NAME>_DISABLE=1` env var or the TTL-bound registry in
`_lib/bypass.py`, both of which leave project source untouched.

Honored markers:
  Same-line:
    // eslint-disable-line
    // eslint-disable
    // @ts-expect-error
    // @ts-ignore
    // @ts-nocheck
    /* @ts-expect-error */
    /* @ts-ignore */
    /* eslint-disable-line */
    // biome-ignore <rule>: <reason>
    // biome-ignore-all <rule>: <reason>
    /* biome-ignore <rule>: <reason> */
    // rome-ignore <rule>: <reason>
    # noqa
    # noqa: E501
    # type: ignore
    # type: ignore[name-defined]
    # pyright: ignore
    # pyright: ignore[reportGeneralTypeIssues]
    # pylint: disable=<rule>
  Preceding-line:
    // eslint-disable-next-line
    /* eslint-disable-next-line */
    // @ts-expect-error
    // @ts-ignore
    // biome-ignore <rule>: <reason>
    // rome-ignore <rule>: <reason>
  Block range:
    /* eslint-disable */ ... /* eslint-enable */
    // eslint-disable     ... // eslint-enable     (line-form not standard but accepted)
  File-level:
    // @ts-nocheck                 (top of file)
    /* eslint-disable */            (single occurrence on its own line)
    # mypy: ignore-errors          (top-of-file mypy file disable)
    # type: ignore                 (top-of-file when sole content of header)
    # ruff: noqa                   (top-of-file ruff file disable)
Public API:
    is_suppressed(lines, i, *, block_state=None, rules=None) -> bool
    line_or_prev_has_suppression(lines, line_no) -> bool
    compute_block_state(lines, *, rules=None) -> BlockState
An eslint directive that names rules is honored only when one of them is in
`rules`; a directive naming no rule is honored for every caller.
    has_top_of_file_marker(lines, marker) -> bool
    has_inline_marker(line, marker) -> bool
    has_ts_nocheck_directive(lines) -> bool
    has_python_file_disable(lines) -> bool
The function never raises. Suppression is best-effort.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field

ESLINT_DIRECTIVE = re.compile(
    r"(?://|/\*)\s*eslint-(disable-next-line|disable-line|disable|enable)"
    r"(?![\w-])([^\n]*)"
)
ESLINT_DIRECTIVE_END = re.compile(r"\*/|\s--(?:\s|$)")
ESLINT_SAME_LINE = "disable-line"
ESLINT_NEXT_LINE = "disable-next-line"
ESLINT_RANGE_OPEN = "disable"
ESLINT_RANGE_CLOSE = "enable"
SAME_LINE_TOKENS = (
    "@ts-expect-error",
    "@ts-ignore",
    "@ts-nocheck",
    "biome-ignore",
    "rome-ignore",
)
PRECEDING_LINE_TOKENS = (
    "@ts-expect-error",
    "@ts-ignore",
    "biome-ignore",
    "rome-ignore",
)
PYTHON_SAME_LINE_PATTERNS = (
    re.compile(r"#\s*noqa(?:\s*:\s*[A-Za-z0-9,\s]+)?\b"),
    re.compile(r"#\s*type\s*:\s*ignore(?:\[[^\]]*\])?"),
    re.compile(r"#\s*pyright\s*:\s*ignore(?:\[[^\]]*\])?"),
    re.compile(r"#\s*pylint\s*:\s*disable\s*=\s*[\w\-,\s]+"),
)
PYTHON_FILE_DISABLE_PATTERNS = (
    re.compile(r"#\s*mypy\s*:\s*ignore-errors"),
    re.compile(r"#\s*ruff\s*:\s*noqa"),
    re.compile(r"#\s*flake8\s*:\s*noqa"),
)
TOP_OF_FILE_SCAN_LIMIT = 10
RESTRICTED_SYNTAX_RULES = frozenset({"no-restricted-syntax"})


@dataclass
class BlockState:
    """Tracks `/* eslint-disable */`-style block ranges."""

    disabled_lines: frozenset[int] = field(default_factory=frozenset)


def compute_block_state(
    lines: list[str], *, rules: frozenset[str] | None = None
) -> BlockState:
    disabled: set[int] = set()
    block_open = False
    for i, line in enumerate(lines):
        kinds = _eslint_kinds(line, rules)
        if block_open and ESLINT_RANGE_CLOSE in kinds:
            block_open = False
            continue
        block_open = block_open or ESLINT_RANGE_OPEN in kinds
        if block_open:
            disabled.add(i)
    return BlockState(disabled_lines=frozenset(disabled))


def _eslint_kinds(line: str, rules: frozenset[str] | None) -> frozenset[str]:
    sanitized = _strip_strings(line)
    return frozenset(
        match.group(1)
        for match in ESLINT_DIRECTIVE.finditer(sanitized)
        if _directive_applies(_directive_rules(match.group(2)), rules)
    )


def _directive_rules(tail: str) -> frozenset[str]:
    end = ESLINT_DIRECTIVE_END.search(tail)
    names = tail[: end.start()] if end else tail
    return frozenset(name.strip() for name in names.split(",") if name.strip())


def _directive_applies(named: frozenset[str], rules: frozenset[str] | None) -> bool:
    if not named:
        return True
    return rules is not None and bool(named & rules)


def _is_lone_block_disable(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("/*") and not stripped.startswith("//"):
        return False
    return ESLINT_RANGE_OPEN in _eslint_kinds(line, None)


def has_inline_marker(line: str, marker: str) -> bool:
    """Detect an exact-token inline marker on `line`.
    Marker must be preceded by `//` or `/*` to count as a real comment-form
    annotation. Substring matches inside string literals are skipped.
    """
    if not marker or marker not in line:
        return False
    sanitized = _strip_strings(line)
    if marker not in sanitized:
        return False
    idx = sanitized.find(marker)
    prefix = sanitized[:idx]
    return "//" in prefix or "/*" in prefix


def has_top_of_file_marker(lines: list[str], marker: str) -> bool:
    """True when `marker` appears in the first non-blank lines of the file.
    Scans up to TOP_OF_FILE_SCAN_LIMIT lines, skipping leading blanks.
    """
    if not marker:
        return False
    seen = 0
    for line in lines:
        if seen >= TOP_OF_FILE_SCAN_LIMIT:
            break
        if not line.strip():
            continue
        seen += 1
        if has_inline_marker(line, marker):
            return True
    return False


def has_python_file_disable(lines: list[str]) -> bool:
    """True when the file opens with a Python file-wide disable directive.
    Recognized markers: `# mypy: ignore-errors`, `# ruff: noqa`, `# flake8: noqa`.
    Scans the first TOP_OF_FILE_SCAN_LIMIT non-blank lines.
    """
    seen = 0
    for line in lines:
        if seen >= TOP_OF_FILE_SCAN_LIMIT:
            break
        if not line.strip():
            continue
        seen += 1
        for pattern in PYTHON_FILE_DISABLE_PATTERNS:
            if pattern.search(line):
                return True
    return False


def _has_python_inline_suppression(line: str) -> bool:
    sanitized = _strip_strings(line)
    return any(p.search(sanitized) for p in PYTHON_SAME_LINE_PATTERNS)


def has_ts_nocheck_directive(lines: list[str]) -> bool:
    """True when `@ts-nocheck` appears at the top of the file as a comment.
    `@ts-nocheck` is the TypeScript directive that disables type checking for
    the entire file. Per project policy, files marked `@ts-nocheck` have
    been deliberately opted out of strict checks; the mutation hook follows
    suit and treats the marker as a file-wide suppression.
    """
    return has_top_of_file_marker(lines, "@ts-nocheck")


def is_suppressed(
    lines: list[str],
    i: int,
    *,
    block_state: BlockState | None = None,
    rules: frozenset[str] | None = None,
) -> bool:
    if i < 0 or i >= len(lines):
        return False
    state = block_state or compute_block_state(lines, rules=rules)
    if i in state.disabled_lines:
        return True
    if _line_suppresses(lines[i], SAME_LINE_TOKENS, ESLINT_SAME_LINE, rules):
        return True
    return i > 0 and _line_suppresses(
        lines[i - 1], PRECEDING_LINE_TOKENS, ESLINT_NEXT_LINE, rules
    )


def _line_suppresses(
    line: str,
    tokens: tuple[str, ...],
    eslint_kind: str,
    rules: frozenset[str] | None,
) -> bool:
    if eslint_kind in _eslint_kinds(line, rules):
        return True
    if _has_python_inline_suppression(line):
        return True
    sanitized = _strip_strings(line)
    if "//" not in sanitized and "/*" not in sanitized:
        return False
    return any(tok in sanitized for tok in tokens)


def line_or_prev_has_suppression(
    lines: list[str],
    line_no: int,
    *,
    rules: frozenset[str] = RESTRICTED_SYNTAX_RULES,
) -> bool:
    return is_suppressed(lines, line_no, rules=rules)


def _strip_strings(line: str) -> str:
    """Mask string contents so substring matches do not pick up code samples.
    Conservative: replaces single-quoted, double-quoted, and backtick-quoted
    spans with whitespace of the same length. Comments stay intact so the
    `//` / `/*` prefix detection still works.
    """
    out: list[str] = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch in ("'", '"', "`"):
            quote = ch
            j = i + 1
            while j < n and line[j] != quote:
                if line[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                j += 1
            out.append(quote + " " * max(0, j - i - 1) + (quote if j < n else ""))
            i = j + 1 if j < n else n
            continue
        out.append(ch)
        i += 1
    return "".join(out)
