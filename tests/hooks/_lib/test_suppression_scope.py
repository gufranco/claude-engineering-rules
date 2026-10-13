from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.suppression import compute_block_state, is_suppressed  # noqa: E402

ANY_RULES = frozenset({"@typescript-eslint/no-explicit-any"})


@pytest.mark.parametrize(
    "lines",
    [
        ["// eslint-disable no-console", "const a = [];", "a.push(1);"],
        ["/* eslint-disable no-console */", "const a = [];", "a.push(1);"],
        ["const a = [];", "a.push(1); // eslint-disable-line no-console"],
        ["const a = [];", "// eslint-disable-next-line no-console", "a.push(1);"],
    ],
)
def test_a_directive_for_another_rule_suppresses_nothing(lines):
    # Arrange
    target = len(lines) - 1

    # Act
    result = is_suppressed(lines, target, block_state=compute_block_state(lines))

    # Assert
    assert result is False


@pytest.mark.parametrize(
    "lines",
    [
        ["// eslint-disable", "const a = [];", "a.push(1);"],
        ["/* eslint-disable */", "const a = [];", "a.push(1);"],
        ["const a = [];", "a.push(1); // eslint-disable-line"],
        ["const a = [];", "// eslint-disable-next-line", "a.push(1);"],
        ["const a = [];", "// eslint-disable-next-line -- reason given", "a.push(1);"],
    ],
)
def test_a_blanket_directive_still_suppresses(lines):
    # Arrange
    target = len(lines) - 1

    # Act
    result = is_suppressed(lines, target, block_state=compute_block_state(lines))

    # Assert
    assert result is True


@pytest.mark.parametrize(
    "directive",
    [
        "// eslint-disable-next-line @typescript-eslint/no-explicit-any",
        "// eslint-disable-next-line no-console, @typescript-eslint/no-explicit-any -- legacy",
    ],
)
def test_a_directive_naming_the_callers_rule_suppresses(directive):
    # Arrange
    lines = [directive, "const x = y as any;"]
    state = compute_block_state(lines, rules=ANY_RULES)

    # Act
    result = is_suppressed(lines, 1, block_state=state, rules=ANY_RULES)

    # Assert
    assert result is True


def test_a_rule_scoped_block_for_the_callers_rule_suppresses():
    # Arrange
    lines = ["/* eslint-disable @typescript-eslint/no-explicit-any */", "let x: any;"]
    state = compute_block_state(lines, rules=ANY_RULES)

    # Act
    result = is_suppressed(lines, 1, block_state=state, rules=ANY_RULES)

    # Assert
    assert result is True
