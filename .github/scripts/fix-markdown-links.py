#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypeVar

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.markdown_link_detector import (  # noqa: E402
    BrokenLinkFinding,
    Finding,
    detect_broken_link_targets,
    detect_findings,
    is_advisory_file,
    tracked_paths,
)


def tracked_markdown_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "*.md"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


LineFinding = TypeVar("LineFinding", Finding, BrokenLinkFinding)

PREVIEW_LIMIT = 3
UNFIXABLE_LIMIT = 20


def _apply_line_edits(
    file_path: Path,
    findings: list[LineFinding],
    edit: Callable[[str, LineFinding], str | None],
) -> int:
    lines = file_path.read_text(encoding="utf-8").split("\n")
    by_line: dict[int, list[LineFinding]] = defaultdict(list)
    for f in findings:
        by_line[f.line].append(f)
    total = 0
    for line_no, line_findings in by_line.items():
        line = lines[line_no - 1]
        for f in sorted(line_findings, key=lambda f: f.column, reverse=True):
            edited = edit(line, f)
            if edited is None:
                continue
            line = edited
            total += 1
        lines[line_no - 1] = line
    file_path.write_text("\n".join(lines), encoding="utf-8")
    return total


def _wrap_token(line: str, f: Finding) -> str | None:
    span_start = f.column - 1
    backtick_end = line.find("`", span_start + 1)
    if backtick_end == -1 or line[span_start + 1 : backtick_end] != f.token:
        return None
    replacement = f"[`{f.token}`]({f.resolved_path})"
    return line[:span_start] + replacement + line[backtick_end + 1 :]


def _retarget_link(line: str, f: BrokenLinkFinding) -> str | None:
    url_start = f.column - 1
    url_end = line.find(")", url_start)
    if url_end == -1:
        return None
    actual_url = line[url_start:url_end]
    if actual_url != f.link_target:
        return None
    fragment = "#" + actual_url.split("#", 1)[1] if "#" in actual_url else ""
    replacement = (f.correct_path or "") + fragment
    return line[:url_start] + replacement + line[url_end:]


def apply_fixes(file_path: Path, findings: list[Finding]) -> int:
    return _apply_line_edits(file_path, findings, _wrap_token)


def apply_broken_target_fixes(
    file_path: Path, findings: list[BrokenLinkFinding]
) -> int:
    return _apply_line_edits(file_path, findings, _retarget_link)


def _parse_args() -> argparse.Namespace:
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
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository whose Markdown is fixed. Defaults to this repository.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the fixes without writing.",
    )
    return parser.parse_args()


def _resolve_files(requested: list[str], root: Path) -> list[str]:
    if requested:
        return [str(Path(f).resolve().relative_to(root)) for f in requested]
    return tracked_markdown_files(root)


def _print_preview(
    header: str, findings: Sequence[Finding | BrokenLinkFinding]
) -> None:
    print(header)
    for f in findings[:PREVIEW_LIMIT]:
        print(f"  {f.render()}")


def _fix_broken(
    path: Path, rel: str, text: str, fixable: list[BrokenLinkFinding], dry_run: bool
) -> tuple[int, str]:
    if not fixable:
        return 0, text
    if dry_run:
        _print_preview(
            f"would rewrite {len(fixable)} broken target(s) in {rel}", fixable
        )
        return len(fixable), text
    applied = apply_broken_target_fixes(path, fixable)
    print(f"rewrote {applied} broken target(s) in {rel}")
    return applied, path.read_text(encoding="utf-8")


def _fix_bare(
    path: Path, rel: str, text: str, tracked: set[str], args: argparse.Namespace
) -> int:
    dry_run = args.dry_run
    findings = detect_findings(text, rel, args.root, tracked=tracked)
    if not findings:
        return 0
    if dry_run:
        _print_preview(
            f"would wrap {len(findings)} bare reference(s) in {rel}", findings
        )
        return len(findings)
    applied = apply_fixes(path, findings)
    print(f"wrapped {applied} bare reference(s) in {rel}")
    return applied


def _fix_file(
    rel: str, args: argparse.Namespace, tracked: set[str]
) -> tuple[int, list[BrokenLinkFinding]]:
    path = args.root / rel
    if is_advisory_file(rel) and not args.include_advisory:
        return 0, []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0, []
    broken = detect_broken_link_targets(text, rel, args.root, tracked=tracked)
    fixable = [f for f in broken if f.correct_path is not None]
    broken_count, text = _fix_broken(path, rel, text, fixable, args.dry_run)
    bare_count = _fix_bare(path, rel, text, tracked, args)
    return broken_count + bare_count, [f for f in broken if f.correct_path is None]


def _report_unfixable(unfixable: list[BrokenLinkFinding]) -> None:
    if not unfixable:
        return
    print()
    print(
        f"WARNING: {len(unfixable)} broken link target(s) point to "
        "files not present in the repo and need manual review:"
    )
    for f in unfixable[:UNFIXABLE_LIMIT]:
        print(f"  {f.render()}")
    if len(unfixable) > UNFIXABLE_LIMIT:
        print(f"  ... and {len(unfixable) - UNFIXABLE_LIMIT} more")


def main() -> int:
    args = _parse_args()
    args.root = args.root.resolve()
    files = _resolve_files(args.files, args.root)
    tracked = tracked_paths(args.root)
    outcomes = [(rel, *_fix_file(rel, args, tracked)) for rel in files]
    grand_total = sum(count for _, count, _ in outcomes)
    touched_files = {rel for rel, count, _ in outcomes if count}
    _report_unfixable([f for _, _, broken in outcomes for f in broken])
    suffix = " (dry run)" if args.dry_run else ""
    print()
    print(
        f"{'Would apply' if args.dry_run else 'Applied'} {grand_total} fix(es) "
        f"across {len(touched_files)} file(s){suffix}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
