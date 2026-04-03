#!/usr/bin/env python3
"""Validate regex patterns in dangerous-command-blocker.py.

Checks:
  - All regex patterns compile without errors
  - No exact duplicate patterns within or across severity levels
  - Reports total pattern count

Exit 0 = all valid, exit 1 = errors found.
"""

import ast
import os
import re
import sys

CLAUDE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCKER_PATH = os.path.join(CLAUDE_DIR, "hooks", "dangerous-command-blocker.py")

PATTERN_LISTS = ["CATASTROPHIC", "CRITICAL_PATHS", "SUSPICIOUS"]


def extract_patterns(source):
    """Extract all regex pattern strings from the blocker source."""
    tree = ast.parse(source)
    patterns = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id not in PATTERN_LISTS:
                continue

            list_name = target.id
            patterns[list_name] = []

            if not isinstance(node.value, ast.List):
                continue

            for elt in node.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    patterns[list_name].append(elt.value)
                elif isinstance(elt, ast.Tuple) and len(elt.elts) >= 1:
                    first = elt.elts[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        patterns[list_name].append(first.value)

    return patterns


def main():
    if not os.path.exists(BLOCKER_PATH):
        print("dangerous-command-blocker.py not found")
        sys.exit(1)

    with open(BLOCKER_PATH) as f:
        source = f.read()

    patterns = extract_patterns(source)
    all_errors = []
    all_patterns = []
    total = 0

    for list_name in PATTERN_LISTS:
        pats = patterns.get(list_name, [])
        total += len(pats)
        print(f"  {list_name}: {len(pats)} patterns")

        for pat in pats:
            try:
                re.compile(pat)
            except re.error as e:
                all_errors.append(f"  {list_name}: invalid regex: {pat!r} -- {e}")

            all_patterns.append((list_name, pat))

    # Check for duplicates across all lists
    seen = {}
    for list_name, pat in all_patterns:
        if pat in seen:
            all_errors.append(
                f"  Duplicate pattern in {list_name} (also in {seen[pat]}): {pat!r}"
            )
        else:
            seen[pat] = list_name

    print(f"\nTotal patterns: {total}")

    if all_errors:
        print(f"\nFAILED: {len(all_errors)} error(s) found:\n")
        for e in all_errors:
            print(e)
        sys.exit(1)
    else:
        print("PASSED: All patterns valid, no duplicates")
        sys.exit(0)


if __name__ == "__main__":
    main()
