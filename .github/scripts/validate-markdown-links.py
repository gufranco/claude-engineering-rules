#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
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


def collect_findings(
    files: list[str], repo_root: Path
) -> tuple[list[Finding], list[BrokenLinkFinding]]:
    bare: list[Finding] = []
    broken: list[BrokenLinkFinding] = []
    tracked = tracked_paths(repo_root)
    for rel in files:
        path_rel = Path(rel)
        path = path_rel if path_rel.is_absolute() else (repo_root / rel)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise SystemExit(f"FAILED: cannot read {rel}: {error}") from error
        bare.extend(detect_findings(text, rel, repo_root, tracked=tracked))
        broken.extend(detect_broken_link_targets(text, rel, repo_root, tracked=tracked))
    return bare, broken


LinkFinding = TypeVar("LinkFinding", Finding, BrokenLinkFinding)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate markdown link discipline across the repo.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Specific files to validate. Default: every tracked .md file.",
    )
    parser.add_argument(
        "--include-advisory",
        action="store_true",
        help="Treat advisory findings (specs/) as blocking too.",
    )
    return parser.parse_args()


def _repo_relative(name: str) -> str:
    resolved = Path(name).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def _split_advisory(
    findings: list[LinkFinding], include_advisory: bool
) -> tuple[list[LinkFinding], list[LinkFinding]]:
    advisory = [
        f for f in findings if is_advisory_file(f.file) and not include_advisory
    ]
    blocking = [
        f for f in findings if not (is_advisory_file(f.file) and not include_advisory)
    ]
    return blocking, advisory


def _print_advisory(
    header: str, findings: Sequence[Finding | BrokenLinkFinding]
) -> None:
    if not findings:
        return
    print(header)
    for f in findings:
        print(f"  {f.render()}")
    print()


def _print_blocking(
    header: str, findings: Sequence[Finding | BrokenLinkFinding], hints: tuple[str, ...]
) -> None:
    if not findings:
        return
    print(header)
    print()
    for f in findings:
        print(f"  {f.render()}")
    print()
    for hint in hints:
        print(hint)
    print()


def _report_blocking(
    blocking_bare: list[Finding], blocking_broken: list[BrokenLinkFinding]
) -> None:
    _print_blocking(
        f"FAILED: {len(blocking_bare)} bare file reference(s) found",
        blocking_bare,
        ("Wrap each reference as: [`<name>`](<path>) or [<name>](<path>)",),
    )
    _print_blocking(
        f"FAILED: {len(blocking_broken)} broken link target(s) found",
        blocking_broken,
        (
            "Rewrite each link target as a path relative to the document.",
            "Auto-fix: python3 .github/scripts/fix-markdown-links.py",
        ),
    )
    print("Rule: rules/markdown-links.md")


def main() -> int:
    args = _parse_args()
    if args.files:
        files = [_repo_relative(f) for f in args.files]
    else:
        files = tracked_markdown_files(REPO_ROOT)
    bare_findings, broken_findings = collect_findings(files, REPO_ROOT)
    blocking_bare, advisory_bare = _split_advisory(bare_findings, args.include_advisory)
    blocking_broken, advisory_broken = _split_advisory(
        broken_findings, args.include_advisory
    )
    _print_advisory(
        f"Advisory: {len(advisory_bare)} bare file reference(s) in specs/",
        advisory_bare,
    )
    _print_advisory(
        f"Advisory: {len(advisory_broken)} broken link target(s) in specs/",
        advisory_broken,
    )
    if not blocking_bare and not blocking_broken:
        print(
            f"PASSED: 0 blocking findings across {len(files)} markdown files "
            "(bare references + broken link targets)."
        )
        return 0
    _report_blocking(blocking_bare, blocking_broken)
    return 1


if __name__ == "__main__":
    sys.exit(main())
