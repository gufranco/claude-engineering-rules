#!/usr/bin/env python3
from __future__ import annotations

import os.path
import re
from dataclasses import dataclass
from pathlib import Path

INLINE_CODE_SPAN = re.compile(r"`([^`\n]+)`")

MARKDOWN_LINK = re.compile(r"\[(?P<text>[^\]\n]*)\]\((?P<url>[^)\n]*)\)")

URL_PATTERN = re.compile(r"https?://\S+|mailto:\S+|ftp://\S+")

FILE_PATH_TOKEN = re.compile(
    r"^"
    r"(?!.*[\s$<>|*?])"
    r"(?![-])"
    r"[A-Za-z0-9_.~][A-Za-z0-9_./~-]*"
    r"$"
)

SKIP_DIR_PREFIXES = (
    "tests/",
    ".github/",
    "tools/",
)
ADVISORY_DIR_PREFIXES = ("specs/", ".work/", ".work-local/")

EXEMPT_FILES = {
    "rules/markdown-links.md",
    "standards/markdown-links.md",
}

GENERIC_FILENAME_TOKENS = frozenset(
    {
        "package.json",
        "package-lock.json",
        "requirements-dev.txt",
        ".pre-commit-config.yaml",
        ".mise.toml",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/ISSUE_TEMPLATE/",
        ".github/ISSUE_TEMPLATE",
    }
)


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    column: int
    token: str
    resolved_path: str

    def render(self) -> str:
        return (
            f"{self.file}:{self.line}:{self.column}: `{self.token}` -> "
            f"existing file at {self.resolved_path}, not linked"
        )


@dataclass(frozen=True)
class BrokenLinkFinding:
    file: str
    line: int
    column: int
    link_text: str
    link_target: str
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
    rel = os.path.relpath(str(target), str(doc_dir))
    return rel.replace(os.sep, "/")


FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})")


def _closes_fence(line: str, m: re.Match[str], open_fence: str) -> bool:
    fence = m.group(1)
    if fence[0] != open_fence[0] or len(fence) < len(open_fence):
        return False
    return not line[m.end() :].strip()


def _fence_ranges(lines: list[str]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    open_fence = ""
    block_start = 0
    for i, line in enumerate(lines, 1):
        m = FENCE_OPEN.match(line)
        if not m:
            continue
        if not open_fence:
            open_fence, block_start = m.group(1), i
        elif _closes_fence(line, m, open_fence):
            ranges.append((block_start, i))
            open_fence = ""
    if open_fence:
        ranges.append((block_start, len(lines)))
    return ranges


def _frontmatter_range(lines: list[str]) -> list[tuple[int, int]]:
    if not lines or lines[0].strip() != "---":
        return []
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return [(1, i + 1)]
    return []


def find_code_block_ranges(text: str) -> list[tuple[int, int]]:
    lines = text.split("\n")
    return [*_fence_ranges(lines), *_frontmatter_range(lines)]


def line_is_inside_ranges(line_no: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= line_no <= end for start, end in ranges)


def find_link_url_ranges(line: str) -> list[tuple[int, int]]:
    return [(m.start("url"), m.end("url")) for m in MARKDOWN_LINK.finditer(line)]


def column_inside_ranges(col: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= col < end for start, end in ranges)


def is_already_linked(line: str, span_start: int, span_end: int) -> bool:
    if span_start >= 1 and line[span_start - 1] == "[":
        after = line[span_end : span_end + 2]
        if after == "](":
            return True

    for m in MARKDOWN_LINK.finditer(line):
        text_start = m.start("text")
        text_end = m.end("text")
        if text_start <= span_start and span_end <= text_end:
            return True

    return False


def is_file_path_token(token: str) -> bool:
    if not token or token.startswith("#") or token.startswith("?"):
        return False
    if len(token) < 3:
        return False
    if " " in token or token.startswith("-"):
        return False
    if token in {".", "..", "./", "../"}:
        return False
    if token in {".git", ".git/", "node_modules", "node_modules/"}:
        return False
    has_dot = "." in token.rsplit("/", 1)[-1]
    has_slash = "/" in token
    if not has_dot and not has_slash:
        return False
    if URL_PATTERN.match(token):
        return False
    return bool(FILE_PATH_TOKEN.match(token))


def resolve_path(token: str, doc_dir: Path, repo_root: Path) -> Path | None:
    candidates: list[Path] = []
    cleaned = token[2:] if token.startswith("./") else token

    if cleaned.startswith("/"):
        return None

    candidates.append((doc_dir / cleaned).resolve())
    candidates.append((repo_root / cleaned).resolve())

    for cand in candidates:
        try:
            cand.relative_to(repo_root)
        except ValueError:
            continue
        if cand.exists():
            return cand
    return None


@dataclass(frozen=True)
class _DocContext:
    rel: str
    doc_dir: Path
    repo_root: Path
    tracked: set[str] | None


def _is_out_of_scope(rel: str) -> bool:
    return rel in EXEMPT_FILES or any(rel.startswith(p) for p in SKIP_DIR_PREFIXES)


def _doc_context(
    file_path: str, repo_root: Path, tracked: set[str] | None
) -> _DocContext:
    path = Path(file_path)
    base = path if path.is_absolute() else repo_root / file_path
    return _DocContext(file_path, base.parent.resolve(), repo_root, tracked)


def _prose_lines(text: str) -> list[tuple[int, str]]:
    code_ranges = find_code_block_ranges(text)
    return [
        (i, line)
        for i, line in enumerate(text.split("\n"), 1)
        if not line_is_inside_ranges(i, code_ranges)
    ]


def _is_candidate_token(
    inner: str, span_start: int, url_ranges: list[tuple[int, int]]
) -> bool:
    if column_inside_ranges(span_start, url_ranges):
        return False
    return is_file_path_token(inner) and inner not in GENERIC_FILENAME_TOKENS


def _span_finding(
    ctx: _DocContext,
    line: str,
    line_no: int,
    m: re.Match[str],
    url_ranges: list[tuple[int, int]],
) -> Finding | None:
    inner = m.group(1)
    if not _is_candidate_token(inner, m.start(), url_ranges):
        return None
    resolved = resolve_path(inner, ctx.doc_dir, ctx.repo_root)
    if resolved is None:
        return None
    if ctx.tracked is not None and not _target_exists(
        resolved, ctx.repo_root, ctx.tracked
    ):
        return None
    if is_already_linked(line, m.start(), m.end()):
        return None
    return Finding(
        file=ctx.rel,
        line=line_no,
        column=m.start() + 1,
        token=inner,
        resolved_path=file_relative_path(resolved, ctx.doc_dir),
    )


def detect_findings(
    text: str,
    file_path: str,
    repo_root: Path,
    *,
    tracked: set[str] | None = None,
) -> list[Finding]:
    if _is_out_of_scope(file_path):
        return []
    ctx = _doc_context(file_path, repo_root, tracked)
    findings: list[Finding] = []
    for i, line in _prose_lines(text):
        url_ranges = find_link_url_ranges(line)
        candidates = (
            _span_finding(ctx, line, i, m, url_ranges)
            for m in INLINE_CODE_SPAN.finditer(line)
        )
        findings.extend(f for f in candidates if f is not None)
    return findings


_LINK_TARGET_SKIP_PREFIXES = ("http://", "https://", "mailto:", "#", "ftp://", "tel:")


def tracked_paths(repo_root: Path) -> set[str]:
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
    try:
        rel = str(candidate.relative_to(repo_root))
    except ValueError:
        return candidate.exists()
    if tracked is None:
        return candidate.exists()
    return rel in tracked


def _inline_code_span_ranges(line: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for m in INLINE_CODE_SPAN.finditer(line):
        ranges.append((m.start(), m.end()))
    return ranges


def _relative_link_target(url: str) -> str | None:
    if not url or url.startswith(_LINK_TARGET_SKIP_PREFIXES):
        return None
    target_no_frag = url.split("#", 1)[0]
    if not target_no_frag:
        return None
    cleaned = target_no_frag[2:] if target_no_frag.startswith("./") else target_no_frag
    return None if cleaned.startswith("/") else cleaned


def _suggested_path(cleaned: str, ctx: _DocContext) -> str | None:
    repo_root_target = (ctx.repo_root / cleaned).resolve()
    if not repo_root_target.is_relative_to(ctx.repo_root):
        return None
    if not _target_exists(repo_root_target, ctx.repo_root, ctx.tracked):
        return None
    return file_relative_path(repo_root_target, ctx.doc_dir)


def _link_finding(
    ctx: _DocContext,
    line_no: int,
    m: re.Match[str],
    code_ranges: list[tuple[int, int]],
) -> BrokenLinkFinding | None:
    if column_inside_ranges(m.start(), code_ranges):
        return None
    url = m.group("url").strip()
    cleaned = _relative_link_target(url)
    if cleaned is None:
        return None
    if _target_exists((ctx.doc_dir / cleaned).resolve(), ctx.repo_root, ctx.tracked):
        return None
    return BrokenLinkFinding(
        file=ctx.rel,
        line=line_no,
        column=m.start("url") + 1,
        link_text=m.group("text"),
        link_target=url,
        correct_path=_suggested_path(cleaned, ctx),
    )


def detect_broken_link_targets(
    text: str,
    file_path: str,
    repo_root: Path,
    *,
    tracked: set[str] | None = None,
) -> list[BrokenLinkFinding]:
    if _is_out_of_scope(file_path):
        return []
    ctx = _doc_context(file_path, repo_root, tracked)
    findings: list[BrokenLinkFinding] = []
    for i, line in _prose_lines(text):
        code_ranges = _inline_code_span_ranges(line)
        candidates = (
            _link_finding(ctx, i, m, code_ranges) for m in MARKDOWN_LINK.finditer(line)
        )
        findings.extend(f for f in candidates if f is not None)
    return findings


def is_advisory_file(file_path: str) -> bool:
    return any(file_path.startswith(p) for p in ADVISORY_DIR_PREFIXES)
