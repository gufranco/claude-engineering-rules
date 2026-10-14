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

SELF_REFERENCE_FILES = (
    "rules/normative-keywords.md",
    "rules/writing-precision.md",
    "standards/normative-keywords.md",
    "standards/writing-precision.md",
    "standards/tone-and-writing.md",
    "CLAUDE.md",
)


BULLET_SHOULD_RE = re.compile(
    r"^\s*(?:[-*]|\d+\.)\s+[Ss]hould\s+\S",
    re.MULTILINE,
)

OPENERS = [
    "Great question!",
    "Sure!",
    "Absolutely!",
    "Of course!",
    "That's a great point",
    "Perfect!",
    "Excellent!",
    "Wonderful!",
]
CLOSERS = [
    "Let me know if you need anything else",
    "Hope this helps",
    "Hope that helps",
    "Feel free to ask",
    "Happy to help",
]
HEDGES = [
    "It's worth noting",
    "It is worth noting",
    "It should be noted",
    "Keep in mind that",
]
TRANSITIONS = [
    "That said,",
    "With that in mind,",
    "Having said that,",
    "On that note,",
]


def _phrase_re(phrases: list[str]) -> re.Pattern[str]:
    return re.compile(r"(?:" + "|".join(re.escape(p) for p in phrases) + r")")


PHRASE_CATEGORIES: list[tuple[str, re.Pattern[str]]] = [
    ("banned-opener", _phrase_re(OPENERS)),
    ("banned-closer", _phrase_re(CLOSERS)),
    ("banned-hedge", _phrase_re(HEDGES)),
    ("banned-transition", _phrase_re(TRANSITIONS)),
]


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


def is_self_reference(rel: str) -> bool:
    return any(rel == p for p in SELF_REFERENCE_FILES)


def _prose_lines(lines: list[str]) -> list[tuple[int, str]]:
    prose: list[tuple[int, str]] = []
    in_code_fence = False
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_fence = not in_code_fence
            continue
        if not in_code_fence:
            prose.append((i, line))
    return prose


def _line_findings(i: int, line: str, skip_phrases: bool) -> list[tuple[int, str, str]]:
    snippet = line.strip()[:120]
    should = [(i, "should-bullet", snippet)] if BULLET_SHOULD_RE.match(line) else []
    if skip_phrases:
        return should
    phrases = [
        (i, label, snippet) for label, pat in PHRASE_CATEGORIES if pat.search(line)
    ]
    return [*should, *phrases]


def scan(path: Path, rel: str) -> list[tuple[int, str, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as error:
        return [(0, "unreadable", f"cannot read: {error}")]
    skip_phrases = is_self_reference(rel)
    return [
        finding
        for i, line in _prose_lines(text.splitlines())
        for finding in _line_findings(i, line, skip_phrases)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate normative keywords.")
    parser.add_argument(
        "--root",
        default=str(CLAUDE_ROOT),
        help="Root directory to scan.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    total_findings = 0

    for path in walk_in_scope(root):
        rel = str(path.relative_to(root))
        findings = scan(path, rel)
        if not findings:
            continue
        print(f"{rel}: {len(findings)} finding(s)")
        for line_no, category, snippet in findings:
            print(f"  {line_no:4d}  [{category}]  {snippet}")
        total_findings += len(findings)

    if total_findings == 0:
        print("Clean: no normative-keyword or banned-phrase findings.")
        return 0
    print(f"\nTotal: {total_findings} finding(s).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
