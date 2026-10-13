from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "hooks"))

from _lib import internal_config_leakage_patterns as patterns  # noqa: E402


def test_path_leak_patterns_flag_a_personal_config_path() -> None:
    # Arrange
    text = "see ~/." + "claude for details"

    # Act
    labels = [label for pat, label in patterns.PATH_LEAK_PATTERNS if pat.search(text)]

    # Assert
    assert labels == ["~/.claude path reference"]


def test_git_message_label_pattern_allows_a_chore_subject() -> None:
    # Arrange
    subject = "chore: bump dependencies"

    # Act
    match = patterns.CONVENTIONAL_LABEL_PATTERN_IN_GIT_MESSAGE.search(subject)

    # Assert
    assert match is None


def test_payload_file_flags_include_every_inline_flag() -> None:
    # Arrange
    inline = patterns.INLINE_PAYLOAD_FILE_FLAGS

    # Act
    missing = [flag for flag in inline if flag not in patterns.PAYLOAD_FILE_FLAGS]

    # Assert
    assert missing == []
