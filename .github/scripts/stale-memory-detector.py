#!/usr/bin/env python3
import os
import re
import sys
import time
from pathlib import Path

BASE_DIR = Path.home() / ".claude" / "projects"
STALE_AFTER_DAYS = 180
SECONDS_PER_DAY = 86400
FILE_REFERENCE = re.compile(r"`(/[^`]+\.(?:ts|js|py|go|rs|md|json|yaml|yml))`")


def find_memory_dirs(base_dir: Path) -> list[Path]:
    if not base_dir.exists():
        return []
    return sorted(
        project / "memory"
        for project in base_dir.iterdir()
        if (project / "memory").is_dir()
    )


def check_memory_file(path: Path, now: float) -> list[str]:
    content = path.read_text(encoding="utf-8")
    missing = [
        f"{path}: references non-existent file: {ref}"
        for ref in FILE_REFERENCE.findall(content)
        if not os.path.exists(ref)
    ]
    age_days = (now - path.stat().st_mtime) / SECONDS_PER_DAY
    stale = (
        [
            f"{path}: last modified {int(age_days)} days ago, "
            "consider reviewing for staleness"
        ]
        if age_days > STALE_AFTER_DAYS
        else []
    )
    lines = [
        line.strip()
        for line in content.split("\n")
        if line.strip() and not line.startswith("---") and not line.startswith("#")
    ]
    empty = (
        [f"{path}: nearly empty, may be a stub or failed write"]
        if len(lines) < 2
        else []
    )
    return [*missing, *stale, *empty]


def memory_files(memory_dirs: list[Path]) -> list[Path]:
    return [
        mem_file
        for mem_dir in memory_dirs
        for mem_file in sorted(mem_dir.glob("*.md"))
        if mem_file.name != "MEMORY.md"
    ]


def main(base_dir: Path = BASE_DIR, now: float | None = None) -> int:
    memory_dirs = find_memory_dirs(base_dir)
    if not memory_dirs:
        print("No memory directories found.")
        return 0

    files = memory_files(memory_dirs)
    clock = time.time() if now is None else now
    warnings = [warning for path in files for warning in check_memory_file(path, clock)]
    print(f"Scanned {len(files)} memory files across {len(memory_dirs)} project(s).")

    if warnings:
        print(f"\n{len(warnings)} potential issues:")
        for warning in warnings:
            print(f"  WARN: {warning}")
        print("\nReview warnings above. No automatic changes were made.")
    else:
        print("All memory files look healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
