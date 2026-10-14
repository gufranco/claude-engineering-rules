from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.comment_syntax import (  # noqa: E402
    CommentFamily,
    added_comment_lines,
    comment_lines,
    document_view,
    is_test_path,
    mask_code,
    notebook_code,
    resolve_family,
    scan_hits,
)


def family_for(path: str) -> CommentFamily:
    family = resolve_family(path)
    assert family is not None, path
    return family


def reported_numbers(pairs: list[tuple[int, str]]) -> tuple[int, ...]:
    return tuple(index + 1 for index, _ in pairs)


__all__ = [
    "CommentFamily",
    "REPO_ROOT",
    "added_comment_lines",
    "comment_lines",
    "document_view",
    "family_for",
    "is_test_path",
    "mask_code",
    "notebook_code",
    "reported_numbers",
    "resolve_family",
    "scan_hits",
]
