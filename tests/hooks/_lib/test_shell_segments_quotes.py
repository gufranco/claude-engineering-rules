from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.shell_segments import (  # noqa: E402
    mask_literal_text,
    quoted_segments,
    strip_heredoc_bodies,
)


@pytest.mark.parametrize(
    "command",
    [
        'echo "a << EOF"\nrm -r build',
        "echo 'a <<EOF'\nrm -r build",
        'printf "%s" "x <<\'EOF\'"\nrm -r build',
        'echo "multi\nline <<EOF"\nrm -r build',
    ],
)
def test_a_heredoc_marker_inside_quotes_keeps_later_lines(command):
    # Arrange
    expected = ["rm", "-r", "build"]

    # Act
    segments = quoted_segments(command)

    # Assert
    assert segments[-1] == expected


def test_a_real_heredoc_body_is_still_dropped():
    # Arrange
    command = "cat <<'EOF' > notes.txt\nmv a b\nEOF\nls"

    # Act
    stripped = strip_heredoc_bodies(command)

    # Assert
    assert stripped == "cat <<'EOF' > notes.txt\nls"


def test_a_quoted_heredoc_marker_does_not_blank_later_lines():
    # Arrange
    command = "echo \"see <<'EOF'\"\nrm -r build"

    # Act
    masked = mask_literal_text(command)

    # Assert
    assert masked.splitlines()[1] == "rm -r build"
