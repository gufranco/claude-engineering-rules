#!/usr/bin/env python3
"""Shared markdown link discipline detector.

Detects bare file-path mentions in markdown that should be wrapped in a
link to the actual file. Used by both the validator at
``scripts/validate-markdown-links.py`` and the hook at
``hooks/markdown-link-discipline.py`` so the two cannot drift.

Rule source: ``rules/markdown-links.md``.
"""

from __future__ import annotations

import os.path
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
    resolved_path: str  # link path, relative to the document's directory

    def render(self) -> str:
        return (
            f"{self.file}:{self.line}:{self.column}: `{self.token}` -> "
            f"existing file at {self.resolved_path}, not linked"
        )


@dataclass(frozen=True)
class BrokenLinkFinding:
    """An existing markdown link whose target file is missing.

    ``correct_path`` is the file-relative path that would resolve to the same
    target when the original link was written as repo-root-relative. None when
    the target does not exist anywhere in the repo.
    """

    file: str  # path of the file containing the link, relative to repo root
    line: int
    column: int  # 1-based column where the link target starts
    link_text: str  # the [text] portion of the link
    link_target: str  # the (target) portion as written
    correct_path: str | None

    def render(self) -> str:
        if self.correct_path:
            suggestion = f" -> rewrite as ({self.correct_path})"
        else:
            suggestion = " (target not found in repo)"
        return (
            f"{self.file}:{self.line}:{self.column}: "
            f"[{self.link_text}]({self.link_target}){suggestion}"
        )


def file_relative_path(target: Path, doc_dir: Path) -> str:
    """Return ``target`` as a path relative to ``doc_dir`` using POSIX separators."""
    rel = os.path.relpath(str(target), str(doc_dir))
    return rel.replace(os.sep, "/")


def find_code_block_ranges(text: str) -> list[tuple[int, int]]:
    """Return a list of (start_line, end_line) for fenced code blocks.

    Both ends are 1-based and inclusive. Follows the CommonMark rule that a
    closing fence must use the same character (backtick or tilde) as the
    opening fence and have at least as many of them. This lets templates
    nest a 3-backtick block inside a 4-backtick block without confusing
    the detector.

    Front-matter blocks delimited by ``---`` at the start of the file are
    also treated as code blocks.
    """
    ranges: list[tuple[int, int]] = []
    lines = text.split("\n")
    fence_open = re.compile(r"^\s*(`{3,}|~{3,})")

    in_block = False
    block_start = 0
    open_char = ""
    open_len = 0

    for i, line in enumerate(lines, 1):
        m = fence_open.match(line)
        if not m:
            continue
        fence = m.group(1)
        if in_block:
            if fence[0] == open_char and len(fence) >= open_len:
                # Ensure the closing fence has no info string.
                rest = line[m.end() :].strip()
                if not rest:
                    ranges.append((block_start, i))
                    in_block = False
                    open_char = ""
                    open_len = 0
        else:
            in_block = True
            block_start = i
            open_char = fence[0]
            open_len = len(fence)

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
    *,
    tracked: set[str] | None = None,
) -> list[Finding]:
    """Run the detector on ``text`` from ``file_path``.

    Returns the list of findings. Empty list when the file is clean.

    Pass ``tracked`` to scope existence checks to the git tree. Without
    it, the detector checks the filesystem (used by ad-hoc input). The
    distinction matters because a bare reference to a gitignored path
    would otherwise be auto-wrapped into a link that 404s in CI.
    """
    rel = file_path
    if rel in EXEMPT_FILES:
        return []
    if any(rel.startswith(p) for p in SKIP_DIR_PREFIXES):
        return []

    if Path(file_path).is_absolute():
        doc_dir = Path(file_path).parent.resolve()
    else:
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
            if tracked is not None and not _target_exists(resolved, repo_root, tracked):
                continue
            if is_already_linked(line, span_start, span_end):
                continue
            findings.append(
                Finding(
                    file=rel,
                    line=i,
                    column=span_start + 1,
                    token=inner,
                    resolved_path=file_relative_path(resolved, doc_dir),
                )
            )

    return findings


_LINK_TARGET_SKIP_PREFIXES = ("http://", "https://", "mailto:", "#", "ftp://", "tel:")


def tracked_paths(repo_root: Path) -> set[str]:
    """Return the set of repo-relative paths tracked by git, plus every
    directory derived from those paths.

    Used as the source of truth for "does this link target exist?" when
    validating cross-document links. A bare filesystem check would let
    gitignored artifacts (logs/, specs/, .last-cleanup, etc.) pass on a
    developer machine but fail in CI where the checkout never had them.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError, FileNotFoundError):
        return set()
    paths: set[str] = set()
    for line in result.stdout.splitlines():
        if not line:
            continue
        paths.add(line)
        parts = line.split("/")
        for i in range(1, len(parts)):
            paths.add("/".join(parts[:i]))
    return paths


def _target_exists(
    candidate: Path,
    repo_root: Path,
    tracked: set[str] | None,
) -> bool:
    """Return True if ``candidate`` is a real link destination.

    When ``tracked`` is provided, membership in the git tree is the
    source of truth. Targets outside the repo always fall back to a
    filesystem check (the tracked set is repo-relative).
    """
    try:
        rel = str(candidate.relative_to(repo_root))
    except ValueError:
        return candidate.exists()
    if tracked is None:
        return candidate.exists()
    return rel in tracked


def _inline_code_span_ranges(line: str) -> list[tuple[int, int]]:
    r"""Return (start, end) character ranges of inline code spans in ``line``.

    Both ends are 0-based indices into the line. Used to skip markdown-link
    pattern matches that fall inside ``\`code\``` spans (e.g. table cells like
    ``\`arr['push'](...)\```).
    """
    ranges: list[tuple[int, int]] = []
    for m in INLINE_CODE_SPAN.finditer(line):
        ranges.append((m.start(), m.end()))
    return ranges


def detect_broken_link_targets(
    text: str,
    file_path: str,
    repo_root: Path,
    *,
    tracked: set[str] | None = None,
) -> list[BrokenLinkFinding]:
    """Return links whose target does not exist when resolved file-relative.

    GitHub resolves markdown link paths relative to the document containing
    the link. A link that uses a repo-root-relative path (e.g. linking to
    ``rules/foo.md`` from inside another ``rules/`` document) 404s on GitHub.
    This detector flags those cases, plus links whose target is missing
    entirely.

    Pass ``tracked`` (a set of repo-relative paths from ``tracked_paths()``)
    to scope the existence check to the git tree. Without it, the detector
    falls back to filesystem existence, which is correct for ad-hoc input
    but lets gitignored paths slip through CI.
    """
    rel = file_path
    if rel in EXEMPT_FILES:
        return []
    if any(rel.startswith(p) for p in SKIP_DIR_PREFIXES):
        return []

    if Path(file_path).is_absolute():
        doc_dir = Path(file_path).parent.resolve()
    else:
        doc_dir = (repo_root / file_path).parent.resolve()
    code_ranges = find_code_block_ranges(text)
    findings: list[BrokenLinkFinding] = []

    for i, line in enumerate(text.split("\n"), 1):
        if line_is_inside_ranges(i, code_ranges):
            continue
        inline_code_ranges = _inline_code_span_ranges(line)
        for m in MARKDOWN_LINK.finditer(line):
            if column_inside_ranges(m.start(), inline_code_ranges):
                continue
            link_text = m.group("text")
            url = m.group("url").strip()
            if not url or url.startswith(_LINK_TARGET_SKIP_PREFIXES):
                continue
            target_no_frag = url.split("#", 1)[0]
            if not target_no_frag:
                continue
            # Trim a leading "./" for cleanliness.
            cleaned = (
                target_no_frag[2:]
                if target_no_frag.startswith("./")
                else target_no_frag
            )
            if cleaned.startswith("/"):
                continue

            # GitHub resolves relative to the document. Try file-relative first.
            file_relative_target = (doc_dir / cleaned).resolve()
            if _target_exists(file_relative_target, repo_root, tracked):
                continue

            # Broken. Check whether the path is fixable by interpreting it as
            # repo-root-relative (the common authoring mistake).
            correct_path: str | None = None
            repo_root_target = (repo_root / cleaned).resolve()
            try:
                repo_root_target.relative_to(repo_root)
            except ValueError:
                pass
            else:
                if _target_exists(repo_root_target, repo_root, tracked):
                    correct_path = file_relative_path(repo_root_target, doc_dir)
            findings.append(
                BrokenLinkFinding(
                    file=rel,
                    line=i,
                    column=m.start("url") + 1,
                    link_text=link_text,
                    link_target=url,
                    correct_path=correct_path,
                )
            )
    return findings


def is_advisory_file(file_path: str) -> bool:
    return any(file_path.startswith(p) for p in ADVISORY_DIR_PREFIXES)
