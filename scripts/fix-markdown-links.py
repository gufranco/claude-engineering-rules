#!/usr/bin/env python3
"""Auto-wrap bare file mentions in markdown.

Uses the shared detector from ``markdown_link_detector.py`` to find
findings, then rewrites each file in place, wrapping every flagged span as
``[`token`](resolved_path)``.

Idempotent: re-running on a clean file produces no changes.

Usage:
    python3 scripts/fix-markdown-links.py
    python3 scripts/fix-markdown-links.py --include-advisory
    python3 scripts/fix-markdown-links.py path/to/file.md ...
    python3 scripts/fix-markdown-links.py --dry-run
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from markdown_link_detector import (  # noqa: E402
    Finding,
    detect_findings,
    is_advisory_file,
)


def tracked_markdown_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "*.md"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def apply_fixes(file_path: Path, findings: list[Finding]) -> int:
    """Rewrite the file, wrapping each bare reference as a link.

    Returns the number of replacements applied.
    """
    if not findings:
        return 0

    text = file_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    by_line: dict[int, list[Finding]] = defaultdict(list)
    for f in findings:
        by_line[f.line].append(f)

    total = 0
    for line_no, line_findings in by_line.items():
        # Process columns in reverse so earlier substitutions do not shift
        # later positions.
        line_findings.sort(key=lambda f: f.column, reverse=True)
        line_idx = line_no - 1
        line = lines[line_idx]
        for f in line_findings:
            span_start = f.column - 1
            backtick_end = line.find("`", span_start + 1)
            if backtick_end == -1:
                continue
            span_end = backtick_end + 1
            actual_content = line[span_start + 1 : backtick_end]
            if actual_content != f.token:
                # Defensive: the detector and the rewriter must agree on the
                # span. If they do not, skip rather than corrupt the file.
                continue
            replacement = f"[`{f.token}`]({f.resolved_path})"
            line = line[:span_start] + replacement + line[span_end:]
            total += 1
        lines[line_idx] = line

    file_path.write_text("\n".join(lines), encoding="utf-8")
    return total


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-wrap bare markdown file mentions as links.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Specific files to fix. Default: every tracked .md file.",
    )
    parser.add_argument(
        "--include-advisory",
        action="store_true",
        help="Also fix files under specs/.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the fixes without writing.",
    )
    args = parser.parse_args()

    if args.files:
        files = [str(Path(f).resolve().relative_to(REPO_ROOT)) for f in args.files]
    else:
        files = tracked_markdown_files(REPO_ROOT)

    grand_total = 0
    touched_files = 0
    for rel in files:
        path = REPO_ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        findings = detect_findings(text, rel, REPO_ROOT)
        if not findings:
            continue
        if is_advisory_file(rel) and not args.include_advisory:
            continue
        if args.dry_run:
            print(f"would fix {len(findings)} reference(s) in {rel}")
            for f in findings[:3]:
                print(f"  {f.render()}")
            grand_total += len(findings)
            touched_files += 1
            continue
        applied = apply_fixes(path, findings)
        if applied:
            print(f"fixed {applied} reference(s) in {rel}")
            grand_total += applied
            touched_files += 1

    suffix = " (dry run)" if args.dry_run else ""
    print()
    print(
        f"{'Would apply' if args.dry_run else 'Applied'} {grand_total} fix(es) "
        f"across {touched_files} file(s){suffix}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
