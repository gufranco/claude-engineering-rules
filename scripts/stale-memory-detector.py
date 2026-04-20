#!/usr/bin/env python3
"""Detect stale memory files in ~/.claude/projects/*/memory/.
A memory file is considered stale when it references a file path or function
that no longer exists in the repository it was created in.
"""

import os
import re
import sys
from pathlib import Path

BASE_DIR = Path.home() / ".claude" / "projects"
ERRORS: list[str] = []
WARNINGS: list[str] = []


def find_memory_dirs() -> list[Path]:
    dirs = []
    if not BASE_DIR.exists():
        return dirs
    for project in BASE_DIR.iterdir():
        mem_dir = project / "memory"
        if mem_dir.is_dir():
            dirs.append(mem_dir)
    return dirs


def check_memory_file(path: Path) -> None:
    with open(path) as f:
        content = f.read()

    # Check for file path references that no longer exist
    # Pattern: backtick-quoted paths or absolute paths
    file_refs = re.findall(r"`(/[^`]+\.(ts|js|py|go|rs|md|json|yaml|yml))`", content)
    for ref, _ in file_refs:
        if not os.path.exists(ref):
            WARNINGS.append(f"{path}: references non-existent file: {ref}")

    # Check for very old memory files (over 180 days)
    age_days = (
        __import__("time").time() - os.path.getmtime(path)
    ) / 86400
    if age_days > 180:
        WARNINGS.append(
            f"{path}: last modified {int(age_days)} days ago — consider reviewing for staleness"
        )

    # Check for empty body
    lines = [l.strip() for l in content.split("\n") if l.strip() and not l.startswith("---") and not l.startswith("#")]
    if len(lines) < 2:
        WARNINGS.append(f"{path}: nearly empty — may be a stub or failed write")


def main() -> None:
    memory_dirs = find_memory_dirs()
    if not memory_dirs:
        print("No memory directories found.")
        return

    total = 0
    for mem_dir in memory_dirs:
        for mem_file in mem_dir.glob("*.md"):
            if mem_file.name == "MEMORY.md":
                continue
            check_memory_file(mem_file)
            total += 1

    print(f"Scanned {total} memory files across {len(memory_dirs)} project(s).")

    if WARNINGS:
        print(f"\n{len(WARNINGS)} potential issues:")
        for w in WARNINGS:
            print(f"  WARN: {w}")

    if ERRORS:
        print(f"\n{len(ERRORS)} errors:")
        for e in ERRORS:
            print(f"  ERROR: {e}")
        sys.exit(1)
    elif WARNINGS:
        print("\nReview warnings above. No automatic changes were made.")
    else:
        print("All memory files look healthy.")


if __name__ == "__main__":
    main()
