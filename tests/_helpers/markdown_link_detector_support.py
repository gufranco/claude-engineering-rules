from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.markdown_link_detector import (  # noqa: E402
    GENERIC_FILENAME_TOKENS,
    BrokenLinkFinding,
    Finding,
    column_inside_ranges,
    detect_broken_link_targets,
    detect_findings,
    file_relative_path,
    find_code_block_ranges,
    find_link_url_ranges,
    is_advisory_file,
    is_already_linked,
    is_file_path_token,
    line_is_inside_ranges,
    resolve_path,
    tracked_paths,
)


__all__ = [
    "BrokenLinkFinding",
    "Finding",
    "GENERIC_FILENAME_TOKENS",
    "REPO_ROOT",
    "column_inside_ranges",
    "detect_broken_link_targets",
    "detect_findings",
    "file_relative_path",
    "find_code_block_ranges",
    "find_link_url_ranges",
    "is_advisory_file",
    "is_already_linked",
    "is_file_path_token",
    "line_is_inside_ranges",
    "resolve_path",
    "tracked_paths",
]
