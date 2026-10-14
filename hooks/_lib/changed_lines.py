from __future__ import annotations

import re
import subprocess
from pathlib import Path

HUNK_HEADER = re.compile(
    r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,(?P<count>\d+))? @@", re.MULTILINE
)
GIT_TIMEOUT_S = 20


def parse_hunks(diff: str) -> frozenset[int]:
    lines: frozenset[int] = frozenset()
    for match in HUNK_HEADER.finditer(diff):
        start = int(match.group("start"))
        count = int(match.group("count") or "1")
        lines = lines | frozenset(range(start, start + count))
    return lines


def _git(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(directory), *args],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_S,
        check=False,
    )


def _is_tracked_with_history(path: Path) -> bool:
    tracked = _git(path.parent, "ls-files", "--error-unmatch", "--", path.name)
    has_head = _git(path.parent, "rev-parse", "--verify", "--quiet", "HEAD")
    return tracked.returncode == 0 and has_head.returncode == 0


def changed_lines(path: Path) -> frozenset[int] | None:
    if not _is_tracked_with_history(path):
        return None
    diff = _git(
        path.parent,
        "diff",
        "-U0",
        "--no-color",
        "--no-ext-diff",
        "HEAD",
        "--",
        path.name,
    )
    if diff.returncode != 0:
        return None
    return parse_hunks(diff.stdout)
