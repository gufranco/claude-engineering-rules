"""Shared suppression helper for ~/.claude hooks.
Centralizes the suppression-scan logic that was duplicated in
`as-any-blocker.py`, `console-log-blocker.py`, and `mutation-method-blocker.py`.
Hooks import this module to recognize standard ignore comments and any
hook-specific allow markers.
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
    // @allow-<category>    (top-of-file allow for this hook category)
    # mypy: ignore-errors          (top-of-file mypy file disable)
    # type: ignore                 (top-of-file when sole content of header)
    # ruff: noqa                   (top-of-file ruff file disable)
Public API:
    is_suppressed(lines, i, *, hook_marker=None, block_state=None) -> bool
    line_or_prev_has_suppression(lines, line_no, *, hook_marker=None) -> bool
    compute_block_state(lines) -> BlockState
    has_top_of_file_marker(lines, marker) -> bool
    has_inline_marker(line, marker) -> bool
    has_justification_trailer(line) -> bool
    has_ts_nocheck_directive(lines) -> bool
    has_python_file_disable(lines) -> bool
The function never raises. Suppression is best-effort.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field

ESLINT_BLOCK_OPEN = re.compile(r"/\*\s*eslint-disable\s*\*/")
ESLINT_BLOCK_CLOSE = re.compile(r"/\*\s*eslint-enable\s*\*/")
ESLINT_LINE_OPEN = re.compile(r"//\s*eslint-disable\b(?!-(?:line|next-line))")
ESLINT_LINE_CLOSE = re.compile(r"//\s*eslint-enable\b")
SAME_LINE_TOKENS = (
    "eslint-disable-line",
    "@ts-expect-error",
    "@ts-ignore",
    "@ts-nocheck",
    "biome-ignore",
    "rome-ignore",
)
PRECEDING_LINE_TOKENS = (
    "eslint-disable-next-line",
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
JUSTIFICATION_TRAILER = re.compile(r"--\s*\S")
TOP_OF_FILE_SCAN_LIMIT = 10


@dataclass
class BlockState:
    """Tracks `/* eslint-disable */`-style block ranges."""

    disabled_lines: frozenset[int] = field(default_factory=frozenset)


def compute_block_state(lines: list[str]) -> BlockState:
    """Scan once and record indices inside any eslint-disable block.
    Indices are zero-based, matching `lines[i]` access. Ranges include the
    opening line and exclude the closing line per ESLint convention.
    """
    disabled: set[int] = set()
    block_open = False
    for i, line in enumerate(lines):
        if not block_open:
            if ESLINT_BLOCK_OPEN.search(line) or _is_lone_block_disable(line):
                block_open = True
                disabled.add(i)
            continue
        if ESLINT_BLOCK_CLOSE.search(line) or ESLINT_LINE_CLOSE.search(line):
            block_open = False
            continue
        disabled.add(i)
    return BlockState(disabled_lines=frozenset(disabled))


def _is_lone_block_disable(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("/*") and not stripped.startswith("//"):
        return False
    if not ESLINT_LINE_OPEN.search(line) and not _looks_like_blanket_disable(line):
        return False
    return True


def _looks_like_blanket_disable(line: str) -> bool:
    if "eslint-disable-line" in line or "eslint-disable-next-line" in line:
        return False
    return "eslint-disable" in line and "enable" not in line


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


def has_justification_trailer(line: str) -> bool:
    """Recognize the ` -- justification` trailer.
    Used to surface advisory warnings when suppressions lack a reason. The
    hook does not enforce the trailer; ESLint does.
    """
    return bool(JUSTIFICATION_TRAILER.search(line))


def is_suppressed(
    lines: list[str],
    i: int,
    *,
    hook_marker: str | None = None,
    block_state: BlockState | None = None,
) -> bool:
    """True when `lines[i]` is covered by any honored suppression form."""
    if i < 0 or i >= len(lines):
        return False
    line = lines[i]
    if block_state is None:
        block_state = compute_block_state(lines)
    if i in block_state.disabled_lines:
        return True
    if hook_marker and has_inline_marker(line, hook_marker):
        return True
    sanitized_line = _strip_strings(line)
    for tok in SAME_LINE_TOKENS:
        if tok in sanitized_line and ("//" in sanitized_line or "/*" in sanitized_line):
            return True
    if _has_python_inline_suppression(line):
        return True
    if i > 0:
        prev = lines[i - 1]
        sanitized_prev = _strip_strings(prev)
        for tok in PRECEDING_LINE_TOKENS:
            if tok in sanitized_prev and (
                "//" in sanitized_prev or "/*" in sanitized_prev
            ):
                return True
        if _has_python_inline_suppression(prev):
            return True
    return False


def line_or_prev_has_suppression(
    lines: list[str],
    line_no: int,
    *,
    hook_marker: str | None = None,
) -> bool:
    """Canonical contract: True when `lines[line_no]` or the preceding line is suppressed.
    This is the
    single entrypoint hooks should call. Internally delegates to `is_suppressed`,
    which already handles preceding-line tokens, block ranges, and Python markers.
    `line_no` is zero-based to match list indexing across hook payloads.
    """
    return is_suppressed(lines, line_no, hook_marker=hook_marker)


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
