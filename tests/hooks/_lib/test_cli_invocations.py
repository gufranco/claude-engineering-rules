from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.cli_invocations import (  # noqa: E402
    Invocation,
    asks_for_help,
    invocations,
    segments,
)


def test_segments_split_on_every_shell_separator():
    # Arrange
    command = "a && b || c; d | e\nf & g"

    # Act
    result = segments(command)

    # Assert
    assert result == ["a", "b", "c", "d", "e", "f", "g"]


def test_segments_flatten_command_substitution():
    # Arrange
    command = "X=$(gh auth token --user a && echo y) gh api user"

    # Act
    result = segments(command)

    # Assert
    assert result == ["X=SUBST gh api user"]


def test_segments_blank_single_quoted_text():
    # Arrange
    command = "echo 'gh api user' && ls"

    # Act
    result = segments(command)

    # Assert
    assert result == ["echo '" + " " * 11 + "'", "ls"]


def test_invocations_record_the_inline_assignments_of_each_call():
    # Arrange
    command = "GH_TOKEN=x gh pr list && gh api user"

    # Act
    result = invocations(command, "gh")

    # Assert
    assert result == [
        Invocation("gh", frozenset({"GH_TOKEN"}), ("pr", "list")),
        Invocation("gh", frozenset(), ("api", "user")),
    ]


def test_invocations_carry_an_earlier_export_forward():
    # Arrange
    command = "export GH_TOKEN=x A=1\ngh api user"

    # Act
    result = invocations(command, "gh")

    # Assert
    assert result == [Invocation("gh", frozenset({"GH_TOKEN", "A"}), ("api", "user"))]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("env GH_TOKEN=x gh api", frozenset({"GH_TOKEN"})),
        ("command gh api", frozenset()),
        ("/usr/local/bin/gh api", frozenset()),
    ],
)
def test_invocations_see_past_prefix_words_and_paths(command, expected):
    # Arrange
    binary = "gh"

    # Act
    result = invocations(command, binary)

    # Assert
    assert [call.assigned for call in result] == [expected]


def test_a_segment_of_only_assignments_is_no_invocation():
    # Arrange
    command = "GH_TOKEN=x A=1"

    # Act
    result = invocations(command, "gh")

    # Assert
    assert result == []


def test_invocations_ignore_other_binaries():
    # Arrange
    command = "ghost run && git push"

    # Act
    result = invocations(command, "gh")

    # Assert
    assert result == []


def test_segments_keep_operators_inside_double_quotes():
    # Arrange
    command = 'rg "a|gh api user" docs && ls'

    # Act
    result = segments(command)

    # Assert
    assert result == ['rg "a|gh api user" docs', "ls"]


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("--help",), True),
        (("pr", "view", "-h"), True),
        (("mr", "note", "1", "-m", "--help"), False),
        (("pr", "list"), False),
        ((), False),
    ],
)
def test_a_help_flag_counts_only_when_no_option_consumes_it(args, expected):
    # Arrange
    call_args = tuple(args)

    # Act
    result = asks_for_help(call_args)

    # Assert
    assert result is expected
