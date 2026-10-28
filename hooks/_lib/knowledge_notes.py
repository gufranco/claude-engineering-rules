from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
from typing import Iterator

DEFAULT_VAULT = "~/second-brain"
REQUIRED_KEYS = ("date", "type", "tags", "ai-first")
PREAMBLE = "## For future agent"

EXEMPT_DIRS = (
    ".obsidian",
    "templates",
    "_trash",
    ".trash",
    "specs",
    "eval",
    "tests",
)
EXEMPT_ROOT_FILES = ("CLAUDE.md", "README.md", "AGENTS.md")
DATED_DIRS = ("daily", "reviews")
RAW_DIR = "raw"
DEFAULT_WINDOW_DAYS = 7

DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}")
DATE_ANYWHERE = re.compile(r"\d{4}-\d{2}(?:-\d{2})?")
STAMP = re.compile(r"\(as of (\d{4})-(\d{2})(?:-(\d{2}))?", re.IGNORECASE)
WIKILINK = re.compile(r"\[\[([^\]|#]+)")
LINK_SPAN = re.compile(r"\[\[[^\]]*\]\]")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
TBD = re.compile(r"\bTBD\b")
URL = re.compile(r"https?://\S+")
TYPED_ID = re.compile(r"\b[a-z][a-z0-9_-]*:[A-Za-z0-9][\w./-]*")
POINTER = re.compile(r"where truth lives", re.IGNORECASE)

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
COPULA = re.compile(
    r"\b(is|are|has|have|holds|sits at|stands at|currently)\b", re.IGNORECASE
)
DIGIT = re.compile(r"(?<![\w.-])\d+(?![\w-])")


def vault_root(raw: str | None = None) -> Path | None:
    value = raw or os.environ.get("SECOND_BRAIN_VAULT") or DEFAULT_VAULT
    root = Path(value).expanduser()
    return root if root.is_dir() else None


def relative(path: Path, root: Path) -> Path | None:
    try:
        return path.resolve().relative_to(root.resolve())
    except (ValueError, OSError, RuntimeError):
        return None


def in_vault(path: str) -> bool:
    if not path:
        return False
    root = vault_root()
    if root is None:
        return False
    return relative(Path(path), root) is not None


def is_exempt(rel: Path) -> bool:
    parts = rel.parts
    if any(part.startswith(".") for part in parts[:-1]):
        return True
    if parts and parts[0] in EXEMPT_DIRS:
        return True
    return len(parts) == 1 and parts[0] in EXEMPT_ROOT_FILES


def is_dated_container(rel: Path) -> bool:
    if rel.parts and rel.parts[0] in DATED_DIRS:
        return True
    return bool(DATE_PREFIX.match(rel.name))


def parse_frontmatter(text: str) -> dict[str, str] | None:
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


def is_timeless(fields: dict[str, str]) -> bool:
    return fields.get("freshness", "").strip().strip("\"'").lower() == "timeless"


def body_after_frontmatter(text: str) -> str:
    match = FRONTMATTER.match(text)
    return text[match.end() :] if match else text


def wikilink_targets(text: str) -> list[str]:
    return [target.strip() for target in WIKILINK.findall(text) if target.strip()]


def iter_notes(root: Path) -> Iterator[tuple[Path, str]]:
    for path in sorted(root.rglob("*.md")):
        rel = relative(path, root)
        if rel is None or is_exempt(rel):
            continue
        try:
            yield rel, path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue


def note_titles(root: Path) -> set[str]:
    return {rel.stem for rel, _text in iter_notes(root)}


def has_stamp(line: str) -> bool:
    return bool(STAMP.search(line))


def stamp_dates(line: str) -> list[date]:
    found: list[date] = []
    for year, month, day in STAMP.findall(line):
        try:
            found.append(date(int(year), int(month), int(day) if day else 1))
        except ValueError:
            continue
    return found


def is_volatile_claim(line: str) -> bool:
    if has_stamp(line):
        return False
    if DATE_PREFIX.match(line.lstrip("-* ")):
        return False
    prose = LINK_SPAN.sub("", line)
    return bool(DIGIT.search(prose) and VOLATILE.search(prose) and COPULA.search(prose))


def walk_lines(body: str) -> Iterator[tuple[int, str, bool]]:
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


def pointer_has_target(line: str) -> bool:
    if URL.search(line):
        return True
    tail = line.split(":", 1)[1] if ":" in line else line
    return bool(TYPED_ID.search(tail))
