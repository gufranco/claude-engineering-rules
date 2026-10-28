#!/usr/bin/env python3
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DECLARING_FILES = ("CLAUDE.md", "README.md")
ITEM_TOLERANCE = 10


def count_checklist_items(path: str) -> tuple[int, int]:
    with open(path, encoding="utf-8") as f:
        content = f.read()

    categories = len(re.findall(r"^###\s+\d+\.\s+", content, re.MULTILINE))
    items = len(re.findall(r"^- \[[ x]\]", content, re.MULTILINE))
    return categories, items


def check_declared_counts(
    path: str, categories: int, items: int, label: str
) -> list[str]:
    with open(path, encoding="utf-8") as f:
        content = f.read()
    category_errors = [
        f"{label}: declares {declared} categories, checklist has {categories}"
        for declared in map(int, re.findall(r"(\d+)\s+categor", content))
        if declared != categories
    ]
    item_errors = [
        f"{label}: declares {declared} items, checklist has {items} (diff > 10)"
        for declared in map(int, re.findall(r"(\d+)\s+items?", content))
        if abs(declared - items) > ITEM_TOLERANCE
    ]
    return [*category_errors, *item_errors]


def main(base_dir: str = BASE_DIR) -> int:
    checklist = os.path.join(base_dir, "checklists", "checklist.md")
    if not os.path.exists(checklist):
        print(f"ERROR: checklist not found at {checklist}", file=sys.stderr)
        return 1

    categories, items = count_checklist_items(checklist)
    print(f"Checklist: {categories} categories, {items} items")

    errors = [
        error
        for name in DECLARING_FILES
        if os.path.exists(path := os.path.join(base_dir, name))
        for error in check_declared_counts(path, categories, items, name)
    ]
    if errors:
        print("\nCount mismatches found:")
        for err in errors:
            print(f"  {err}")
        return 1

    print("All count declarations match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
