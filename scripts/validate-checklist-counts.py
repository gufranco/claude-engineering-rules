#!/usr/bin/env python3
"""Validate that checklist.md category count matches the declared total in CLAUDE.md and README.md."""

import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CHECKLIST = os.path.join(BASE_DIR, "checklists", "checklist.md")
CLAUDE_MD = os.path.join(BASE_DIR, "CLAUDE.md")
README_MD = os.path.join(BASE_DIR, "README.md")

ERRORS = []


def count_checklist_items(path: str) -> tuple[int, int]:
    """Return (category_count, item_count) from checklist.md."""
    with open(path) as f:
        content = f.read()

    categories = len(re.findall(r"^###\s+\d+\.\s+", content, re.MULTILINE))
    items = len(re.findall(r"^- \[[ x]\]", content, re.MULTILINE))
    return categories, items


def check_declared_counts(path: str, categories: int, items: int, label: str) -> None:
    with open(path) as f:
        content = f.read()

    # Look for "N categories" or "N items" or "N-category"
    cat_matches = re.findall(r"(\d+)\s+categor", content)
    item_matches = re.findall(r"(\d+)\s+items?", content)

    for m in cat_matches:
        declared = int(m)
        if declared != categories:
            ERRORS.append(
                f"{label}: declares {declared} categories, checklist has {categories}"
            )

    for m in item_matches:
        declared = int(m)
        if abs(declared - items) > 10:  # allow small drift
            ERRORS.append(
                f"{label}: declares {declared} items, checklist has {items} (diff > 10)"
            )


def main() -> None:
    if not os.path.exists(CHECKLIST):
        print(f"ERROR: checklist not found at {CHECKLIST}", file=sys.stderr)
        sys.exit(1)

    categories, items = count_checklist_items(CHECKLIST)
    print(f"Checklist: {categories} categories, {items} items")

    if os.path.exists(CLAUDE_MD):
        check_declared_counts(CLAUDE_MD, categories, items, "CLAUDE.md")

    if os.path.exists(README_MD):
        check_declared_counts(README_MD, categories, items, "README.md")

    if ERRORS:
        print("\nCount mismatches found:")
        for err in ERRORS:
            print(f"  {err}")
        sys.exit(1)

    print("All count declarations match.")


if __name__ == "__main__":
    main()
