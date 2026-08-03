#!/usr/bin/env python3
"""Preserve and restore context across Claude Code compaction.

Hook surfaces:
    - SessionStart / PreCompact: snapshot `git status` + current branch.
    - SessionStart resume / PostCompact: print the saved snapshot back.

Usage: `compact-context-saver.py [pre|post]`. Defaults to `pre`.

Snapshots are scoped to the project they describe. The default location is
`~/.claude/.compact-context.d/<project-digest>.snapshot`, keyed by the git
toplevel (or cwd when outside a repo). `post` prints a snapshot only when its
recorded `Project:` matches the current project and the file is newer than
`MAX_AGE_SECONDS`. A snapshot taken in one project can therefore never surface
in another. Setting `$CLAUDE_COMPACT_CONTEXT` overrides the path; the project
and freshness checks still apply.

Bypass channels:
    1. Env var `COMPACT_CONTEXT_DISABLE=1`.
    2. File registry entry for hook `compact-context-saver`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.bypass import is_bypassed  # noqa: E402

HOOK_NAME = "compact-context-saver"
ENV_DISABLE = "COMPACT_CONTEXT_DISABLE"
ENV_PATH = "CLAUDE_COMPACT_CONTEXT"
SNAPSHOT_DIR_NAME = ".compact-context.d"
LEGACY_FILE_NAME = ".compact-context"
PROJECT_FIELD = "Project:"
DIGEST_LENGTH = 16
GIT_TIMEOUT_SECONDS = 3
MAX_AGE_SECONDS = 24 * 60 * 60


def _claude_home() -> Path:
    return Path.home() / ".claude"


def _session_id() -> str:
    return (
        os.environ.get("CLAUDE_CODE_SESSION_ID")
        or os.environ.get("CLAUDE_SESSION_ID")
        or os.environ.get("SESSION_ID")
        or "unknown"
    )


def _run_git(*args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _project_root() -> Path:
    result = _run_git("rev-parse", "--show-toplevel")
    if result is not None and result.returncode == 0:
        toplevel = result.stdout.strip()
        if toplevel:
            return Path(toplevel).resolve()
    return Path.cwd().resolve()


def _project_digest(project: Path) -> str:
    return hashlib.sha256(str(project).encode("utf-8")).hexdigest()[:DIGEST_LENGTH]


def _snapshot_path(project: Path) -> Path:
    override = os.environ.get(ENV_PATH)
    if override:
        return Path(override)
    return _claude_home() / SNAPSHOT_DIR_NAME / f"{_project_digest(project)}.snapshot"


def _git_branch() -> str:
    result = _run_git("branch", "--show-current")
    if result is None:
        return "unknown"
    branch = result.stdout.strip()
    return branch if branch else "unknown"


def _git_status() -> str:
    result = _run_git("status", "--porcelain")
    if result is None or result.returncode != 0:
        return "  not a git repo"
    return result.stdout.rstrip("\n")


def _snapshot_project(body: str) -> str:
    for line in body.splitlines():
        if line.startswith(PROJECT_FIELD):
            return line[len(PROJECT_FIELD) :].strip()
    return ""


def _is_fresh(path: Path, now: float) -> bool:
    try:
        modified_at = path.stat().st_mtime
    except OSError:
        return False
    return (now - modified_at) <= MAX_AGE_SECONDS


def retire_legacy_snapshot() -> None:
    if os.environ.get(ENV_PATH):
        return
    legacy = _claude_home() / LEGACY_FILE_NAME
    try:
        legacy.unlink(missing_ok=True)
    except OSError as error:
        sys.stderr.write(f"{HOOK_NAME}: could not remove {legacy}: {error}\n")


def save_context(path: Path, project: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
    body = [
        "=== Compact Context Snapshot ===",
        f"Timestamp: {timestamp}",
        f"{PROJECT_FIELD} {project}",
        f"Session: {_session_id()}",
        f"Branch: {_git_branch()}",
        "",
        "Modified files:",
        _git_status(),
        "",
    ]
    path.write_text("\n".join(body), encoding="utf-8")


def restore_context(path: Path, project: Path) -> None:
    if not path.is_file():
        return
    if not _is_fresh(path, time.time()):
        return
    try:
        body = path.read_text(encoding="utf-8")
    except OSError as error:
        sys.stderr.write(f"{HOOK_NAME}: could not read {path}: {error}\n")
        return
    if _snapshot_project(body) != str(project):
        return
    sys.stdout.write("Context preserved before compaction:\n")
    sys.stdout.write(body)


def main(argv: list[str]) -> int:
    if os.environ.get(ENV_DISABLE) == "1" or is_bypassed(HOOK_NAME):
        return 0
    subcommand = argv[0] if argv else "pre"
    if subcommand not in {"pre", "post"}:
        sys.stderr.write(f"Usage: {sys.argv[0]} [pre|post]\n")
        return 1
    project = _project_root()
    path = _snapshot_path(project)
    if subcommand == "pre":
        retire_legacy_snapshot()
        save_context(path, project)
        return 0
    restore_context(path, project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
