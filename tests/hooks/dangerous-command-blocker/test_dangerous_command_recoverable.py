from __future__ import annotations

import re
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[3] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.dangerous_command_recoverable import RECOVERABLE  # noqa: E402

EXPECTED_ENTRY_COUNT = 11


def test_recoverable_patterns_all_compile() -> None:
    # Arrange
    patterns = [pattern for pattern, _guidance in RECOVERABLE]

    # Act
    compiled = [re.compile(pattern) for pattern in patterns]

    # Assert
    assert len(compiled) == EXPECTED_ENTRY_COUNT
