#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKIPPED_DIRS = frozenset({".git", "node_modules", ".venv"})
FENCE = re.compile(r"^\s*(```|~~~)")
CODE_SPAN = re.compile(r"`[^`\n]*`")
CHECKS = (
    ("provenance heading", re.compile(r"^#{1,6}\s+Provenance\b")),
    (
        "dated change",
        re.compile(
            r"\b(?:Added|Amended|Promoted|Decided|Adopted|Seen|Measured|Verified|Fetched|Origin)\b"
            r"[^.\n]{0,30}?\b20\d\d-\d\d-\d\d\b"
        ),
    ),
    (
        "attribution",
        re.compile(
            r"by direct user instruction|\bowner (?:request|decision)\b|"
            r"\bat the (?:user|owner)'s request\b|"
            r"\bthe (?:user|owner) (?:corrected|flagged|rejected)\b",
            re.I,
        ),
    ),
    ("cross-repository pull request", re.compile(r"\b[\w.-]+/[\w.-]+ ?#\d+\b")),
)


@dataclass(frozen=True, slots=True)
class Finding:
    path: str
    line: int
    kind: str
    text: str


def markdown_files(root: Path) -> list[str]:
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "*.md"],
        capture_output=True,
        text=True,
        check=False,
    )
    if listed.returncode == 0:
        return [line for line in listed.stdout.splitlines() if line]
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*.md")
        if not SKIPPED_DIRS.intersection(path.relative_to(root).parts)
    )


def prose_lines(text: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append((number, CODE_SPAN.sub("", line)))
    return lines


def file_findings(root: Path, relative: str) -> list[Finding]:
    try:
        text = (root / relative).read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        return [Finding(relative, 0, "unreadable", str(error)[:120])]
    return [
        Finding(relative, number, kind, line.strip()[:120])
        for number, line in prose_lines(text)
        for kind, pattern in CHECKS
        if pattern.search(line)
    ]


def findings(root: Path) -> list[Finding]:
    return [
        finding
        for relative in markdown_files(root)
        if (root / relative).is_file()
        for finding in file_findings(root, relative)
    ]


def check(root: Path) -> int:
    found = findings(root)
    if not found:
        print(
            "PASSED: no change history, attribution, or cross-repository references in tracked Markdown."
        )
        return 0
    for finding in found:
        print(f"{finding.path}:{finding.line}: {finding.kind}: {finding.text}")
    print(
        f"FAILED: {len(found)} line(s) publish work history. A repository file states "
        "only the current rule; the history belongs in the vault. See "
        "standards/rule-provenance.md."
    )
    return 1


def main() -> int:
    return check(REPO_ROOT)


if __name__ == "__main__":
    sys.exit(main())
