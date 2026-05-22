#!/usr/bin/env python3
"""Validate markdown link discipline across the repo.

Scans every tracked ``.md`` file and reports bare file mentions whose path
resolves to a real file in the repo. The rule is documented in
``rules/markdown-links.md``.

Exit code 0 when clean. Exit code 1 when any blocking finding is present.
Advisory findings (paths under ``specs/``) print to stdout but do not fail.

Usage:
    python3 scripts/validate-markdown-links.py
    python3 scripts/validate-markdown-links.py --include-advisory
    python3 scripts/validate-markdown-links.py path/to/file.md ...
"""

from __future__ import annotations

import argparse
import subprocess
import sys
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
    tracked_paths,
)


def tracked_markdown_files(repo_root: Path) -> list[str]:
    """Return repo-relative paths of every tracked .md file."""
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
        except (OSError, UnicodeDecodeError):
            continue
        bare.extend(detect_findings(text, rel, repo_root, tracked=tracked))
        broken.extend(detect_broken_link_targets(text, rel, repo_root, tracked=tracked))
    return bare, broken


def main() -> int:
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
    args = parser.parse_args()

    if args.files:
        files = []
        for f in args.files:
            resolved = Path(f).resolve()
            try:
                files.append(str(resolved.relative_to(REPO_ROOT)))
            except ValueError:
                # Path is outside the repo. Use the absolute path so callers
                # can validate ad-hoc files such as temporary test fixtures.
                files.append(str(resolved))
    else:
        files = tracked_markdown_files(REPO_ROOT)

    bare_findings, broken_findings = collect_findings(files, REPO_ROOT)
    blocking_bare: list[Finding] = []
    advisory_bare: list[Finding] = []
    blocking_broken: list[BrokenLinkFinding] = []
    advisory_broken: list[BrokenLinkFinding] = []

    for f in bare_findings:
        if is_advisory_file(f.file) and not args.include_advisory:
            advisory_bare.append(f)
        else:
            blocking_bare.append(f)

    for bf in broken_findings:
        if is_advisory_file(bf.file) and not args.include_advisory:
            advisory_broken.append(bf)
        else:
            blocking_broken.append(bf)

    if advisory_bare:
        print(f"Advisory: {len(advisory_bare)} bare file reference(s) in specs/")
        for f in advisory_bare:
            print(f"  {f.render()}")
        print()

    if advisory_broken:
        print(f"Advisory: {len(advisory_broken)} broken link target(s) in specs/")
        for bf in advisory_broken:
            print(f"  {bf.render()}")
        print()

    if not blocking_bare and not blocking_broken:
        print(
            f"PASSED: 0 blocking findings across {len(files)} markdown files "
            "(bare references + broken link targets)."
        )
        return 0

    if blocking_bare:
        print(f"FAILED: {len(blocking_bare)} bare file reference(s) found")
        print()
        for f in blocking_bare:
            print(f"  {f.render()}")
        print()
        print("Wrap each reference as: [`<name>`](<path>) or [<name>](<path>)")
        print()

    if blocking_broken:
        print(f"FAILED: {len(blocking_broken)} broken link target(s) found")
        print()
        for bf in blocking_broken:
            print(f"  {bf.render()}")
        print()
        print("Rewrite each link target as a path relative to the document.")
        print("Auto-fix: python3 scripts/fix-markdown-links.py")
        print()

    print("Rule: rules/markdown-links.md")
    return 1


if __name__ == "__main__":
    sys.exit(main())
