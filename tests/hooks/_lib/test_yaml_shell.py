from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.comment_regions import line_starts  # noqa: E402
from _lib.yaml_shell import yaml_shell_ranges  # noqa: E402


def shell_text(text: str) -> list[str]:
    return [
        text[start:end] for start, end in yaml_shell_ranges(text, line_starts(text))
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("run: echo hi\n", ["echo hi"]),
        ("run: 'echo hi'\n", ["echo hi"]),
        ("run: |\n  a\n  b\nnext: 1\n", ["  a\n  b"]),
        ("script:\n  - a\n  - 'b'\n", ["a", "b"]),
        ("cmds:\n  - cmd: c\n  - task: t\n", ["c"]),
        ("command: [a, b]\n", []),
        ("run: |\nnext: 1\n", []),
        ("command:\n  - a\n", []),
        ("script:\n  - |\n\n    x\n", ["\n    x\n"]),
    ],
)
def test_extracts_the_shell_text_of_each_shell_key(
    text: str, expected: list[str]
) -> None:
    # Arrange
    document = text

    # Act
    found = shell_text(document)

    # Assert
    assert found == expected
