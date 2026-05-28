#!/usr/bin/env python3
"""validate-normative-keywords.py

Short, focused validator for normative-keyword and banned-phrase drift in
rules, standards, checklists, and CLAUDE.md. Runs locally before commits or
on demand. Complements the broader audit-writing-quality.py by surfacing
only the findings authors should act on right away.

Scope:
  ~/.claude/rules/
  ~/.claude/standards/
  ~/.claude/checklists/
  ~/.claude/CLAUDE.md

Categories checked:
  should-bullet       bullet items starting with "Should " or "should "
  banned-opener       sycophantic openers outside quoted definitions
  banned-closer       rhetorical closers
  banned-hedge        hedge phrases
  banned-transition   weak transitions

Exit code:
  0  no actionable findings
  1  one or more findings printed to stdout

Source rules:
  ~/.claude/rules/normative-keywords.md
  ~/.claude/rules/writing-precision.md
  ~/.claude/CLAUDE.md Banned Phrases
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

SELF_REFERENCE_FILES = (
    "rules/normative-keywords.md",
    "rules/writing-precision.md",
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


def scan(path: Path, rel: str) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return findings

    if is_self_reference(rel):
        # Skip phrase detection in files that define or quote the patterns.
        # Should-bullet detection still applies.
        skip_phrases = True
    else:
        skip_phrases = False

    lines = text.splitlines()
    in_code_fence = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue

        if BULLET_SHOULD_RE.match(line):
            findings.append((i, "should-bullet", line.strip()[:120]))

        if skip_phrases:
            continue

        for label, pat in PHRASE_CATEGORIES:
            m = pat.search(line)
            if m:
                findings.append((i, label, line.strip()[:120]))

    return findings


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
