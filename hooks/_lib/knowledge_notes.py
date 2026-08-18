"""Shared primitives for reading and checking second brain vault notes.

One source of truth for the note grammar. The write-time hook imports it to
decide single-file questions; the vault linters import it to walk the whole
graph. Anything both need lives here so the two can never drift.

Rule source: ``rules/knowledge-notes.md``.
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
from typing import Iterator

DEFAULT_VAULT = "~/Dropbox/Obsidian/Second Brain"
REQUIRED_KEYS = ("date", "type", "tags", "ai-first")
PREAMBLE = "## For future agent"

EXEMPT_DIRS = (".obsidian", "templates", "_trash", ".trash")
EXEMPT_ROOT_FILES = ("CLAUDE.md", "README.md", "AGENTS.md")
DATED_DIRS = ("daily", "reviews")
RAW_DIR = "raw"
DEFAULT_WINDOW_DAYS = 7

DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}")
DATE_ANYWHERE = re.compile(r"\d{4}-\d{2}(?:-\d{2})?")
STAMP = re.compile(r"\(as of (\d{4})-(\d{2})(?:-(\d{2}))?", re.IGNORECASE)
WIKILINK = re.compile(r"\[\[([^\]|#]+)")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
TBD = re.compile(r"\bTBD\b")
URL = re.compile(r"https?://\S+")
TYPED_ID = re.compile(r"\b[a-z][a-z0-9_-]*:[A-Za-z0-9][\w./-]*")

VOLATILE_WORDS = (
    "deal",
    "deals",
    "ticket",
    "tickets",
    "user",
    "users",
    "customer",
    "customers",
    "subscriber",
    "subscribers",
    "request",
    "requests",
    "error",
    "errors",
    "incident",
    "incidents",
    "member",
    "members",
    "employee",
    "employees",
    "task",
    "tasks",
    "row",
    "rows",
    "record",
    "records",
    "instance",
    "instances",
    "replica",
    "replicas",
    "node",
    "nodes",
    "balance",
    "revenue",
    "mrr",
    "arr",
    "follower",
    "followers",
    "star",
    "stars",
    "download",
    "downloads",
    "headcount",
    "backlog",
    "pipeline",
)
VOLATILE = re.compile(r"\b(" + "|".join(VOLATILE_WORDS) + r")\b", re.IGNORECASE)
COPULA = re.compile(r"\b(is|are|has|have|holds|sits at|stands at|currently)\b", re.IGNORECASE)
DIGIT = re.compile(r"(?<![\w.-])\d+(?![\w-])")


def vault_root(raw: str | None = None) -> Path | None:
    """Return the vault root, or None when it does not exist on disk."""
    value = raw or os.environ.get("SECOND_BRAIN_VAULT") or DEFAULT_VAULT
    try:
        root = Path(value).expanduser()
    except (OSError, ValueError):  # pragma: no cover
        return None
    return root if root.is_dir() else None


def relative(path: Path, root: Path) -> Path | None:
    """Return `path` relative to `root`, or None when it falls outside."""
    try:
        return path.resolve().relative_to(root.resolve())
    except (ValueError, OSError, RuntimeError):
        return None


def is_exempt(rel: Path) -> bool:
    """Return True for paths the specification does not govern."""
    parts = rel.parts
    if parts and parts[0] in EXEMPT_DIRS:
        return True
    return len(parts) == 1 and parts[0] in EXEMPT_ROOT_FILES


def is_dated_container(rel: Path) -> bool:
    """Return True when the note is itself a dated snapshot."""
    if rel.parts and rel.parts[0] in DATED_DIRS:
        return True
    return bool(DATE_PREFIX.match(rel.name))


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Return top-level frontmatter keys, or None when the block is absent."""
    match = FRONTMATTER.match(text)
    if not match:
        return None
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if line.startswith((" ", "\t", "-")) or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def body_after_frontmatter(text: str) -> str:
    """Return the note body with any frontmatter block removed."""
    match = FRONTMATTER.match(text)
    return text[match.end() :] if match else text


def wikilink_targets(text: str) -> list[str]:
    """Return every wikilink target, aliases and anchors stripped."""
    return [target.strip() for target in WIKILINK.findall(text) if target.strip()]


def iter_notes(root: Path) -> Iterator[tuple[Path, str]]:
    """Yield every governed markdown note as a (relative path, text) pair."""
    try:
        candidates = sorted(root.rglob("*.md"))
    except OSError:  # pragma: no cover
        return
    for path in candidates:
        rel = relative(path, root)
        if rel is None or is_exempt(rel):
            continue
        try:
            yield rel, path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):  # pragma: no cover
            continue


def note_titles(root: Path) -> set[str]:
    """Return the stem of every governed note, which is its wikilink target."""
    return {rel.stem for rel, _text in iter_notes(root)}


def has_stamp(line: str) -> bool:
    """Return True when the line carries an as-of recency stamp."""
    return bool(STAMP.search(line))


def stamp_dates(line: str) -> list[date]:
    """Return every parseable as-of date on the line."""
    found: list[date] = []
    for year, month, day in STAMP.findall(line):
        try:
            found.append(date(int(year), int(month), int(day) if day else 1))
        except ValueError:
            continue
    return found


def is_volatile_claim(line: str) -> bool:
    """Return True for an undated present-tense claim about a moving subject."""
    if has_stamp(line):
        return False
    if DATE_PREFIX.match(line.lstrip("-* ")):
        return False
    return bool(DIGIT.search(line) and VOLATILE.search(line) and COPULA.search(line))


def walk_lines(body: str) -> Iterator[tuple[int, str, bool]]:
    """Yield (line number, stripped text, under a dated heading) for prose lines.

    Fenced blocks, blank lines, and headings are consumed rather than yielded,
    so every caller sees the same view of what counts as a claim.
    """
    in_fence = False
    under_dated_heading = False
    for number, raw_line in enumerate(body.splitlines(), start=1):
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line:
            continue
        if line.startswith("#"):
            under_dated_heading = bool(DATE_ANYWHERE.search(line))
            continue
        yield number, line, under_dated_heading
