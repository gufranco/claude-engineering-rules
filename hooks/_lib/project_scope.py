"""Repository-boundary helpers for hooks that resolve project context.

A hook that walks up from a directory to find a config file, a plan, a test
directory, or a schema must stop at the repository it is inside. Without that
boundary the walk reaches the home directory, where whatever the machine
happens to hold governs every project on it.

That failure is silent and machine-wide: the outer match wins for projects that
have nothing to do with it, and no error names the cause.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

GIT_MARKER = ".git"


def repo_root(start: Path) -> Path | None:
    """Return the nearest ancestor holding a git marker, or None outside a repo.

    The marker is a directory in a normal checkout and a file in a worktree or
    a submodule, so both are accepted.
    """
    try:
        cursor = start.resolve()
    except OSError:  # pragma: no cover
        return None
    while True:
        if (cursor / GIT_MARKER).exists():
            return cursor
        if cursor == cursor.parent:
            return None
        cursor = cursor.parent


def walk_up(start: Path, limit: int, stop_at_repo_root: bool = True) -> Iterator[Path]:
    """Yield `start` and its ancestors, nearest first.

    Stops after `limit` directories, at the filesystem root, and, by default,
    at the repository root. Yielding nearest first lets a caller prefer the
    closest match rather than the most recently modified one.
    """
    try:
        cursor = start.resolve()
    except OSError:  # pragma: no cover
        return
    boundary = repo_root(cursor) if stop_at_repo_root else None
    for _ in range(limit):
        yield cursor
        if boundary is not None and cursor == boundary:
            return
        if cursor == cursor.parent:
            return
        cursor = cursor.parent
