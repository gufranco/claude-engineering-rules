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
    BrokenLinkFinding,
    Finding,
    detect_broken_link_targets,
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


def apply_broken_target_fixes(
    file_path: Path, findings: list[BrokenLinkFinding]
) -> int:
    """Rewrite each fixable broken-target link to its file-relative form.

    Findings whose ``correct_path`` is None are skipped: the target does not
    exist in the repo and needs manual review.
    """
    fixable = [f for f in findings if f.correct_path is not None]
    if not fixable:
        return 0

    text = file_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    by_line: dict[int, list[BrokenLinkFinding]] = defaultdict(list)
    for f in fixable:
        by_line[f.line].append(f)

    total = 0
    for line_no, line_findings in by_line.items():
        # Process columns in reverse so earlier substitutions do not shift
        # later positions on the same line.
        line_findings.sort(key=lambda f: f.column, reverse=True)
        line_idx = line_no - 1
        line = lines[line_idx]
        for f in line_findings:
            url_start = f.column - 1
            # The URL portion ends at the next ')' on the line. Anchors are
            # preserved by splitting on '#'.
            url_end = line.find(")", url_start)
            if url_end == -1:
                continue
            actual_url = line[url_start:url_end]
            if actual_url != f.link_target:
                # Defensive: detector and rewriter must agree on the span.
                continue
            # Preserve any fragment (#anchor) on the original target.
            fragment = ""
            if "#" in actual_url:
                fragment = "#" + actual_url.split("#", 1)[1]
            replacement = (f.correct_path or "") + fragment
            line = line[:url_start] + replacement + line[url_end:]
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
    touched_files: set[str] = set()
    unfixable_broken: list[BrokenLinkFinding] = []

    for rel in files:
        path = REPO_ROOT / rel
        if is_advisory_file(rel) and not args.include_advisory:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # Fix broken existing link targets first. The bare-reference detector
        # below would otherwise be confused by links whose URL still points to
        # a non-resolving path.
        broken = detect_broken_link_targets(text, rel, REPO_ROOT)
        fixable_broken = [f for f in broken if f.correct_path is not None]
        unfixable_broken.extend(f for f in broken if f.correct_path is None)

        if fixable_broken:
            if args.dry_run:
                print(f"would rewrite {len(fixable_broken)} broken target(s) in {rel}")
                for f in fixable_broken[:3]:
                    print(f"  {f.render()}")
                grand_total += len(fixable_broken)
                touched_files.add(rel)
            else:
                applied = apply_broken_target_fixes(path, fixable_broken)
                if applied:
                    print(f"rewrote {applied} broken target(s) in {rel}")
                    grand_total += applied
                    touched_files.add(rel)
                # Re-read after rewrite for the bare-reference pass.
                text = path.read_text(encoding="utf-8")

        # Wrap bare references.
        findings = detect_findings(text, rel, REPO_ROOT)
        if not findings:
            continue
        if args.dry_run:
            print(f"would wrap {len(findings)} bare reference(s) in {rel}")
            for f in findings[:3]:
                print(f"  {f.render()}")
            grand_total += len(findings)
            touched_files.add(rel)
            continue
        applied = apply_fixes(path, findings)
        if applied:
            print(f"wrapped {applied} bare reference(s) in {rel}")
            grand_total += applied
            touched_files.add(rel)

    if unfixable_broken:
        print()
        print(
            f"WARNING: {len(unfixable_broken)} broken link target(s) point to "
            "files not present in the repo and need manual review:"
        )
        for f in unfixable_broken[:20]:
            print(f"  {f.render()}")
        if len(unfixable_broken) > 20:
            print(f"  ... and {len(unfixable_broken) - 20} more")

    suffix = " (dry run)" if args.dry_run else ""
    print()
    print(
        f"{'Would apply' if args.dry_run else 'Applied'} {grand_total} fix(es) "
        f"across {len(touched_files)} file(s){suffix}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
