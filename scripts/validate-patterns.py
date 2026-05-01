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

# Lists treated as known and required. Other ALL_CAPS list assignments are
# discovered automatically so the validator follows the hook source instead of
# a hand-maintained allowlist.
KNOWN_LISTS = {"CATASTROPHIC", "CRITICAL_PATHS", "SUSPICIOUS", "SAFE_CLEANUP"}


def discover_pattern_lists(tree: ast.AST) -> set[str]:
    discovered: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            name = target.id
            if not name.isupper():
                continue
            if not isinstance(node.value, ast.List):
                continue
            for elt in node.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    discovered.add(name)
                    break
                if isinstance(elt, ast.Tuple) and elt.elts:
                    first = elt.elts[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        discovered.add(name)
                        break
    return discovered


def extract_patterns(source):
    tree = ast.parse(source)
    discovered = discover_pattern_lists(tree)
    pattern_lists = sorted(discovered)
    patterns: dict[str, list[str]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id not in pattern_lists:
                continue

            list_name = target.id
            patterns[list_name] = []
            if not isinstance(node.value, ast.List):
                continue

            for elt in node.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    patterns[list_name].append(elt.value)
                elif isinstance(elt, ast.Tuple) and elt.elts:
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

    discovered_names = sorted(patterns.keys())
    missing_required = KNOWN_LISTS - set(discovered_names)
    if missing_required:
        all_errors.append(
            f"  Required pattern list(s) missing from blocker: {sorted(missing_required)}"
        )

    for list_name in discovered_names:
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
