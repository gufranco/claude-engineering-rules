#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Iterable


CLAUDE_ROOT = Path(__file__).resolve().parents[2]

IN_SCOPE_DIRS = ("rules", "standards", "checklists")
EXTRA_FILES = ("CLAUDE.md",)


PRONOUN_LEADING_RE = re.compile(
    r"^\s*(?:[-*]|\d+\.)\s+(It|This|They|That|These|Those)\b",
)


COMMON_IRREGULAR_PARTICIPLES = (
    "set",
    "made",
    "done",
    "given",
    "taken",
    "sent",
    "kept",
    "held",
    "shown",
    "built",
    "written",
    "read",
    "found",
    "left",
    "lost",
    "told",
    "said",
    "seen",
    "thrown",
)

PASSIVE_RE = re.compile(
    r"\b(?:is|are|was|were|be|been|being)\s+(?:[a-z]+ed|"
    + "|".join(COMMON_IRREGULAR_PARTICIPLES)
    + r")\b",
)

ACTOR_HINT_RES = (re.compile(r"\bby\s+(?:the\s+)?[A-Za-z]"),)


def _phrase_has_actor(line: str) -> bool:
    return any(p.search(line) for p in ACTOR_HINT_RES)


def _has_multiple_nouns(prev_line: str) -> bool:
    if not prev_line.strip():
        return False
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]*", prev_line)
    candidates = [w for w in words if len(w) > 3]
    return len(set(candidates)) >= 2


def walk_in_scope(root: Path) -> Iterable[Path]:
    for d in IN_SCOPE_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames if not x.startswith(".")]
            for name in filenames:
                if name.lower().endswith(".md"):
                    yield Path(dirpath) / name
    for name in EXTRA_FILES:
        path = root / name
        if path.is_file():
            yield path


def _prose_with_previous(lines: list[str]) -> list[tuple[int, str, str]]:
    prose: list[tuple[int, str, str]] = []
    in_code_fence = False
    prev_line = ""
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_fence = not in_code_fence
            prev_line = ""
            continue
        if not in_code_fence:
            prose.append((i, line, prev_line))
        prev_line = line
    return prose


def _line_findings(i: int, line: str, prev_line: str) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []
    if PRONOUN_LEADING_RE.match(line) and _has_multiple_nouns(prev_line):
        findings.append((i, "pronoun-leading", line.strip()[:120]))
    is_bullet = re.match(r"^\s*(?:[-*]|\d+\.)\s+", line)
    if is_bullet and PASSIVE_RE.search(line) and not _phrase_has_actor(line):
        findings.append((i, "passive-bullet", line.strip()[:120]))
    return findings


def scan(path: Path) -> list[tuple[int, str, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as error:
        return [(0, "unreadable", f"cannot read: {error}")]
    return [
        finding
        for i, line, prev_line in _prose_with_previous(text.splitlines())
        for finding in _line_findings(i, line, prev_line)
    ]


def _parse_root() -> Path:
    parser = argparse.ArgumentParser(description="Validate clarity heuristics.")
    parser.add_argument(
        "--root",
        default=str(CLAUDE_ROOT),
        help="Root directory to scan.",
    )
    return Path(parser.parse_args().root).resolve()


def _print_findings(rel: str, findings: list[tuple[int, str, str]]) -> None:
    print(f"{rel}: {len(findings)} finding(s)")
    for line_no, category, snippet in findings:
        print(f"  {line_no:4d}  [{category}]  {snippet}")


def main() -> int:
    root = _parse_root()
    total = 0
    unreadable = 0
    for path in walk_in_scope(root):
        rel = str(path.relative_to(root))
        findings = scan(path)
        if not findings:
            continue
        _print_findings(rel, findings)
        total += len(findings)
        unreadable += sum(1 for _, category, _ in findings if category == "unreadable")
    if unreadable:
        print(f"\nFAILED: {unreadable} file(s) could not be read.")
        return 1
    if total == 0:
        print("Clean: no clarity findings.")
    else:
        print(
            f"\nTotal: {total} finding(s). Advisory only; review and rewrite where appropriate."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
