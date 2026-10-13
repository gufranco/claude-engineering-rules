from __future__ import annotations

from pathlib import Path
from typing import Iterator

GIT_MARKER = ".git"


def repo_root(start: Path) -> Path | None:
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
