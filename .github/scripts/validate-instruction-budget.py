#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

HARNESS_LIMIT_CHARS = 150_000
BUDGET_CHARS = 120_000
LARGEST_FILES_SHOWN = 5
IMPORT_LINE = re.compile(r"^@(\S+)\s*$", re.MULTILINE)
REPO_ROOT = Path(__file__).resolve().parents[2]


def always_loaded_files(root: Path) -> list[Path]:
    claude_md = root / "CLAUDE.md"
    files = [claude_md] if claude_md.is_file() else []
    if files:
        imports = IMPORT_LINE.findall(claude_md.read_text(encoding="utf-8"))
        files.extend(
            target for target in (root / name for name in imports) if target.is_file()
        )
    files.extend(sorted((root / "rules").rglob("*.md")))
    return files


def total_chars(files: list[Path]) -> int:
    return sum(len(path.read_text(encoding="utf-8")) for path in files)


def check(root: Path, budget: int) -> int:
    files = always_loaded_files(root)
    total = total_chars(files)
    print(
        f"Always-loaded instructions: {total:,} chars across {len(files)} files "
        f"(budget {budget:,}, harness limit {HARNESS_LIMIT_CHARS:,})"
    )
    if total <= budget:
        print("PASSED")
        return 0
    largest = sorted(
        files, key=lambda path: len(path.read_text(encoding="utf-8")), reverse=True
    )[:LARGEST_FILES_SHOWN]
    print(f"FAILED: {total - budget:,} chars over budget. Largest files:")
    for path in largest:
        size = len(path.read_text(encoding="utf-8"))
        print(f"  {size:>7,}  {path.relative_to(root).as_posix()}")
    print(
        "Move detail into the matching standards/ file and keep only the core "
        "in rules/. See standards/rules-vs-standards.md."
    )
    return 1


def main() -> int:
    return check(REPO_ROOT, BUDGET_CHARS)


if __name__ == "__main__":
    sys.exit(main())
