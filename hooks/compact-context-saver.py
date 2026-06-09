#!/usr/bin/env python3
"""Preserve and restore context across Claude Code compaction.

Hook surfaces:
    - SessionStart / PreCompact: snapshot `git status` + current branch.
    - SessionStart resume / PostCompact: print the saved snapshot back.

Usage: `compact-context-saver.py [pre|post]`. Defaults to `pre`.

Snapshot path: `$CLAUDE_COMPACT_CONTEXT` if set, else `~/.claude/.compact-context`.

Bypass channels:
    1. Env var `COMPACT_CONTEXT_DISABLE=1`.
    2. File registry entry for hook `compact-context-saver`.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.bypass import is_bypassed  # noqa: E402

HOOK_NAME = "compact-context-saver"
ENV_DISABLE = "COMPACT_CONTEXT_DISABLE"
ENV_PATH = "CLAUDE_COMPACT_CONTEXT"
DEFAULT_PATH = Path.home() / ".claude" / ".compact-context"
GIT_TIMEOUT_SECONDS = 3


def _snapshot_path() -> Path:
    override = os.environ.get(ENV_PATH)
    return Path(override) if override else DEFAULT_PATH


def _git_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "unknown"
    branch = result.stdout.strip()
    return branch if branch else "unknown"


def _git_status() -> str:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "  not a git repo"
    if result.returncode != 0:
        return "  not a git repo"
    return result.stdout.rstrip("\n")


def save_context(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
    body = [
        "=== Compact Context Snapshot ===",
        f"Timestamp: {timestamp}",
        f"Branch: {_git_branch()}",
        "",
        "Modified files:",
        _git_status(),
        "",
    ]
    path.write_text("\n".join(body), encoding="utf-8")


def restore_context(path: Path) -> None:
    if not path.is_file():
        return
    sys.stdout.write("Context preserved before compaction:\n")
    sys.stdout.write(path.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    if os.environ.get(ENV_DISABLE) == "1" or is_bypassed(HOOK_NAME):
        return 0
    subcommand = argv[0] if argv else "pre"
    path = _snapshot_path()
    if subcommand == "pre":
        save_context(path)
        return 0
    if subcommand == "post":
        restore_context(path)
        return 0
    sys.stderr.write(f"Usage: {sys.argv[0]} [pre|post]\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
