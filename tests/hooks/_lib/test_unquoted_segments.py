from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.shell_segments import unquoted_segments  # noqa: E402


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("a && b || c; d | e", ["a ", " b ", " c", " d ", " e"]),
        ("grep 'x\\|y' f && ls", ["grep 'x\\|y' f ", " ls"]),
        ('echo "a; b" | wc', ['echo "a; b" ', " wc"]),
        ('git commit -m "one\ntwo"\nls', ['git commit -m "one\ntwo"', "ls"]),
        ("sleep 1 & ls", ["sleep 1 ", " ls"]),
        ("\nls; pwd", ["ls", " pwd"]),
        ("cat <<'EOF' > f\nit's\nEOF\nls", ["cat <<'EOF' > f\nit's\nEOF", "ls"]),
    ],
)
def test_operators_inside_quotes_do_not_split(command, expected):
    # Arrange
    text = command

    # Act
    segments = unquoted_segments(text)

    # Assert
    assert segments == expected
