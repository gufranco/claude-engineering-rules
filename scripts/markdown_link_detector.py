#!/usr/bin/env python3
"""Shared markdown link discipline detector.

Detects bare file-path mentions in markdown that should be wrapped in a
link to the actual file. Used by both the validator at
``scripts/validate-markdown-links.py`` and the hook at
``hooks/markdown-link-discipline.py`` so the two cannot drift.

Rule source: ``rules/markdown-links.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Match a single backticked span that contains a token plausibly representing
# a file path. The match group is the inner content.
INLINE_CODE_SPAN = re.compile(r"`([^`\n]+)`")

# A markdown link is `[text](url)`. We capture the URL so we can recognize
# that the surrounding span is already linked.
MARKDOWN_LINK = re.compile(r"\[(?P<text>[^\]\n]*)\]\((?P<url>[^)\n]*)\)")

# Bare URL or fragment. We must not flag tokens inside a markdown link URL.
URL_PATTERN = re.compile(r"https?://\S+|mailto:\S+|ftp://\S+")

# File-path-like tokens. Restrictive on purpose so we do not flag plain words.
# Acceptable forms:
#   foo.ext
#   foo/bar.ext
#   foo/bar/                (trailing slash, directory)
#   foo/bar                 (no extension, treated only when a real directory)
# Reject content that contains a space, a shell prompt sigil, or option flags.
FILE_PATH_TOKEN = re.compile(
    r"^"
    r"(?!.*[\s$<>|*?])"  # no spaces, shell sigils, or wildcards
    r"(?![-])"  # do not start with a dash (option flag)
    r"[A-Za-z0-9_.~][A-Za-z0-9_./~-]*"
    r"$"
)

# Skip directories whose markdown is allowed to show bare paths.
SKIP_DIR_PREFIXES = (
    "tests/",
    "scripts/",
    ".github/",
    "tools/",
)
# Spec folders are advisory only. The validator can be configured to ignore.
ADVISORY_DIR_PREFIXES = ("specs/",)

# Files explicitly exempt by name.
EXEMPT_FILES = {
    "rules/markdown-links.md",
}


@dataclass(frozen=True)
class Finding:
    """A bare file-path reference that should be linked."""

    file: str  # path relative to repo root
    line: int
    column: int  # 1-based column of the backticked span
    token: str  # the inner content of the backticked span
    resolved_path: str  # path-resolved location of the actual file

    def render(self) -> str:
        return (
            f"{self.file}:{self.line}:{self.column}: `{self.token}` -> "
            f"existing file at {self.resolved_path}, not linked"
        )


def find_code_block_ranges(text: str) -> list[tuple[int, int]]:
    """Return a list of (start_line, end_line) for fenced code blocks.

    Both ends are 1-based and inclusive. Front-matter blocks delimited by
    ``---`` at the start of the file are also treated as code blocks.
    """
    ranges: list[tuple[int, int]] = []
    lines = text.split("\n")
    in_block = False
    block_start = 0
    fence_pattern = re.compile(r"^\s*```")

    for i, line in enumerate(lines, 1):
        if fence_pattern.match(line):
            if in_block:
                ranges.append((block_start, i))
                in_block = False
            else:
                in_block = True
                block_start = i

    # Unclosed fence: include to end of file.
    if in_block:
        ranges.append((block_start, len(lines)))

    # Front-matter at top of file.
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                ranges.append((1, i + 1))
                break

    return ranges


def line_is_inside_ranges(line_no: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= line_no <= end for start, end in ranges)


def find_link_url_ranges(line: str) -> list[tuple[int, int]]:
    """Return (start, end) character ranges within a single line that fall
    inside the URL portion of a markdown link ``[text](url)``."""
    return [(m.start("url"), m.end("url")) for m in MARKDOWN_LINK.finditer(line)]


def column_inside_ranges(col: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= col < end for start, end in ranges)


def is_already_linked(line: str, span_start: int, span_end: int) -> bool:
    r"""Determine whether the inline-code span at [span_start:span_end] is
    wrapped in a markdown link, either as ``[`token`](url)`` (backticks inside
    the link text) or ``[token](url)`` referencing the same token.

    The span boundaries refer to the full ``\`token\``` span including the
    backticks.
    """
    # Pattern 1: backticks inside link text. Search for `[` immediately before
    # the span and `](` immediately after the span.
    if span_start >= 1 and line[span_start - 1] == "[":
        after = line[span_end : span_end + 2]
        if after == "](":
            return True

    # Pattern 2: the token sits inside a link text without backticks. This is
    # uncommon for file paths because the link text would lose the monospace
    # styling. We do not flag in this case to avoid double-counting.
    for m in MARKDOWN_LINK.finditer(line):
        # If our span is entirely inside the text portion of the link, the
        # token is already part of a linked phrase.
        text_start = m.start("text")
        text_end = m.end("text")
        if text_start <= span_start and span_end <= text_end:
            return True

    return False


def is_file_path_token(token: str) -> bool:
    """Decide whether ``token`` looks like a file path or directory."""
    if not token or token.startswith("#") or token.startswith("?"):
        return False
    # Tokens must have at least 3 characters of substance so we do not match
    # shell arguments like ``.`` or ``..`` or single-letter aliases.
    if len(token) < 3:
        return False
    # Reject anything that has a space, a shell sigil, or an option flag.
    if " " in token or token.startswith("-"):
        return False
    # Reject lone directory tokens that are common shell shorthand.
    if token in {".", "..", "./", "../"}:
        return False
    # Reject paths that exist on disk but should never be linked from docs.
    # These are typically VCS metadata or build artifacts that, while real,
    # do not render usefully as documentation links on GitHub.
    if token in {".git", ".git/", "node_modules", "node_modules/"}:
        return False
    # Reject pure CLI command names without any path-like signal.
    has_dot = "." in token.rsplit("/", 1)[-1]
    has_slash = "/" in token
    if not has_dot and not has_slash:
        return False
    # Reject URLs.
    if URL_PATTERN.match(token):
        return False
    return bool(FILE_PATH_TOKEN.match(token))


def resolve_path(token: str, doc_dir: Path, repo_root: Path) -> Path | None:
    """Resolve ``token`` relative to ``doc_dir`` first, then ``repo_root``.

    Returns the resolved path when it exists in the repo, otherwise None.
    """
    candidates: list[Path] = []
    # Trim a leading "./" for cleanliness.
    cleaned = token[2:] if token.startswith("./") else token

    # Reject absolute paths leaving the repo (defensive).
    if cleaned.startswith("/"):
        return None

    candidates.append((doc_dir / cleaned).resolve())
    candidates.append((repo_root / cleaned).resolve())

    for cand in candidates:
        try:
            # Ensure resolved path is inside the repo.
            cand.relative_to(repo_root)
        except ValueError:
            continue
        if cand.exists():
            return cand
    return None


def detect_findings(
    text: str,
    file_path: str,
    repo_root: Path,
) -> list[Finding]:
    """Run the detector on ``text`` from ``file_path``.

    Returns the list of findings. Empty list when the file is clean.
    """
    rel = file_path
    if rel in EXEMPT_FILES:
        return []
    if any(rel.startswith(p) for p in SKIP_DIR_PREFIXES):
        return []

    doc_dir = (repo_root / file_path).parent.resolve()
    code_ranges = find_code_block_ranges(text)
    findings: list[Finding] = []

    for i, line in enumerate(text.split("\n"), 1):
        if line_is_inside_ranges(i, code_ranges):
            continue
        link_url_ranges = find_link_url_ranges(line)
        for m in INLINE_CODE_SPAN.finditer(line):
            inner = m.group(1)
            span_start = m.start()
            span_end = m.end()
            # Skip if the span is inside a markdown link URL fragment.
            if column_inside_ranges(span_start, link_url_ranges):
                continue
            if not is_file_path_token(inner):
                continue
            resolved = resolve_path(inner, doc_dir, repo_root)
            if resolved is None:
                continue
            if is_already_linked(line, span_start, span_end):
                continue
            findings.append(
                Finding(
                    file=rel,
                    line=i,
                    column=span_start + 1,
                    token=inner,
                    resolved_path=str(resolved.relative_to(repo_root)),
                )
            )

    return findings


def is_advisory_file(file_path: str) -> bool:
    return any(file_path.startswith(p) for p in ADVISORY_DIR_PREFIXES)
