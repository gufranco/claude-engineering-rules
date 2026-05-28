#!/usr/bin/env python3
"""validate-clarity.py

Advisory on-demand validator for the pronoun-discipline and active-voice
sections of `rules/writing-precision.md`. Surfaces lines that likely contain
ambiguous pronouns or bullet-level passive voice. Conservative heuristics by
design: false positives are tolerated, false negatives are not catastrophic.

Scope:
  ~/.claude/rules/
  ~/.claude/standards/
  ~/.claude/checklists/
  ~/.claude/CLAUDE.md

Categories:
  pronoun-leading    Bullet or sentence starts with It/This/They/That and the
                     prior line has two or more noun-shaped tokens.
  passive-bullet     Bullet item that uses `is/are/was/were/be/been X-ed`
                     without naming an actor.

Exit code:
  0 always. The script is advisory.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Iterable


CLAUDE_ROOT = Path.home() / ".claude"

IN_SCOPE_DIRS = ("rules", "standards", "checklists")
EXTRA_FILES = ("CLAUDE.md",)


PRONOUN_LEADING_RE = re.compile(
    r"^\s*(?:[-*]|\d+\.)\s+(It|This|They|That|These|Those)\b",
)


# Catch typical English passive constructions on bullet lines.
# Matches forms like: "is processed", "are validated", "was set",
# "were stored", "be created", "been deleted".
# A simple heuristic: a form of "to be" followed by a past participle
# ending in -ed (regular verbs) or matching a small list of common
# irregular forms.
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

# Active-voice indicators on the same line allow a passive-leaning phrase to
# pass: an actor is named. Common patterns: "by X", "calls", "runs", "writes".
ACTOR_HINT_RES = (re.compile(r"\bby\s+(?:the\s+)?[A-Za-z]"),)


def _phrase_has_actor(line: str) -> bool:
    return any(p.search(line) for p in ACTOR_HINT_RES)


def _has_multiple_nouns(prev_line: str) -> bool:
    """Heuristic: does the previous line contain at least two noun-shaped
    tokens? We approximate with: count of words starting with a capital
    letter (proper nouns) plus distinct lowercase words longer than 3
    characters. Catches enough cases to make the pronoun-leading flag
    useful without flooding the report.
    """
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


def scan(path: Path) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return findings

    lines = text.splitlines()
    in_code_fence = False
    prev_line = ""

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_fence = not in_code_fence
            prev_line = ""
            continue
        if in_code_fence:
            prev_line = line
            continue

        # Pronoun-leading bullets when the prior line has multiple nouns.
        m = PRONOUN_LEADING_RE.match(line)
        if m and _has_multiple_nouns(prev_line):
            findings.append((i, "pronoun-leading", line.strip()[:120]))

        # Passive voice in bullet lines without an explicit actor hint.
        if re.match(r"^\s*(?:[-*]|\d+\.)\s+", line):
            if PASSIVE_RE.search(line) and not _phrase_has_actor(line):
                findings.append((i, "passive-bullet", line.strip()[:120]))

        prev_line = line

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate clarity heuristics.")
    parser.add_argument(
        "--root",
        default=str(CLAUDE_ROOT),
        help="Root directory to scan.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    total = 0

    for path in walk_in_scope(root):
        rel = str(path.relative_to(root))
        findings = scan(path)
        if not findings:
            continue
        print(f"{rel}: {len(findings)} finding(s)")
        for line_no, category, snippet in findings:
            print(f"  {line_no:4d}  [{category}]  {snippet}")
        total += len(findings)

    if total == 0:
        print("Clean: no clarity findings.")
    else:
        print(
            f"\nTotal: {total} finding(s). Advisory only; review and rewrite where appropriate."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
