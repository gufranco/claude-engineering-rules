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
    Finding,
    detect_findings,
    is_advisory_file,
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


def collect_findings(files: list[str], repo_root: Path) -> list[Finding]:
    all_findings: list[Finding] = []
    for rel in files:
        path = repo_root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        all_findings.extend(detect_findings(text, rel, repo_root))
    return all_findings


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
        files = [str(Path(f).resolve().relative_to(REPO_ROOT)) for f in args.files]
    else:
        files = tracked_markdown_files(REPO_ROOT)

    findings = collect_findings(files, REPO_ROOT)
    blocking: list[Finding] = []
    advisory: list[Finding] = []

    for f in findings:
        if is_advisory_file(f.file) and not args.include_advisory:
            advisory.append(f)
        else:
            blocking.append(f)

    if advisory:
        print(f"Advisory: {len(advisory)} bare file reference(s) in specs/")
        for f in advisory:
            print(f"  {f.render()}")
        print()

    if not blocking:
        print(
            f"PASSED: 0 blocking bare file references across {len(files)} markdown files."
        )
        return 0

    print(f"FAILED: {len(blocking)} bare file reference(s) found")
    print()
    for f in blocking:
        print(f"  {f.render()}")
    print()
    print("Wrap each reference as: [`<name>`](<path>) or [<name>](<path>)")
    print("Rule: rules/markdown-links.md")
    return 1


if __name__ == "__main__":
    sys.exit(main())
