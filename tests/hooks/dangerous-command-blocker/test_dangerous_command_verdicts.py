from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[3] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.dangerous_command_verdicts import (  # noqa: E402
    first_notice,
    targets_protected,
)

PATTERNS = [(r"\bdanger\b", "danger guidance"), (r"\bother\b", "other guidance")]


def test_first_notice_keeps_only_the_first_match() -> None:
    # Arrange
    command = "danger other"

    # Act
    result = first_notice(command, command, PATTERNS, "WARNING: ")

    # Assert
    assert result == ["WARNING: danger guidance\nCommand: danger other"]


@pytest.mark.parametrize(
    ("matched", "branch", "expected"),
    [
        ("git push origin main", "feature", True),
        ("git push origin feature", "main", False),
        ("git push", "develop", True),
        ("git push", "feature", False),
    ],
)
def test_targets_protected_reads_ref_and_branch(
    matched: str, branch: str, expected: bool
) -> None:
    # Arrange
    current = branch

    # Act
    result = targets_protected(matched, current)

    # Assert
    assert result is expected
