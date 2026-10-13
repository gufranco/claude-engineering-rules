from __future__ import annotations
import sys
from pathlib import Path
import pytest
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
from _lib.suppression import (  # noqa: E402
    BlockState,
    compute_block_state,
    has_inline_marker,
    has_python_file_disable,
    has_top_of_file_marker,
    has_ts_nocheck_directive,
    is_suppressed,
    line_or_prev_has_suppression,
)


@pytest.mark.parametrize(
    "lines,target,expected",
    [
        (["// eslint-disable-next-line", "items.push(v)"], 1, True),
        (["items.push(v) // eslint-disable-line"], 0, True),
        (["items.push(v) // @ts-ignore"], 0, True),
        (["// @ts-expect-error", "items.push(v)"], 1, True),
        (["items.push(v)"], 0, False),
        (["// biome-ignore lint/style/useConst: legacy", "items.push(v)"], 1, True),
        (["items.push(v) // biome-ignore lint: x"], 0, True),
        (["// rome-ignore lint/security: x", "items.push(v)"], 1, True),
        (["arr.append(x)  # noqa"], 0, True),
        (["arr.append(x)  # noqa: E501"], 0, True),
        (["arr.append(x)  # type: ignore"], 0, True),
        (["arr.append(x)  # type: ignore[name-defined]"], 0, True),
        (["arr.append(x)  # pyright: ignore"], 0, True),
        (["arr.append(x)  # pylint: disable=no-member"], 0, True),
    ],
)
def test_is_suppressed_marker_combinations(
    lines: list[str], target: int, expected: bool
) -> None:
    # Arrange
    block_state = compute_block_state(lines)

    # Act
    actual = is_suppressed(lines, target, block_state=block_state)

    # Assert
    assert actual is expected


def test_eslint_block_disable_covers_lines_in_range() -> None:
    # Arrange
    lines = [
        "/* eslint-disable */",
        "arr.push(a)",
        "arr.push(b)",
        "/* eslint-enable */",
        "arr.push(c)",
    ]

    # Act
    state = compute_block_state(lines)

    # Assert
    assert state.disabled_lines == frozenset({0, 1, 2})


def test_block_state_dataclass_default_is_empty() -> None:
    # Arrange
    empty: frozenset[int] = frozenset()

    # Act
    state = BlockState()

    # Assert
    assert state.disabled_lines == empty


def test_string_literal_does_not_count_as_marker() -> None:
    # Arrange
    lines = ['const msg = "// eslint-disable-line not real";']

    # Act
    actual = is_suppressed(lines, 0)

    # Assert
    assert actual is False


def test_has_inline_marker_requires_comment_prefix() -> None:
    # Arrange
    line = 'const tag = "@ts-ignore"'

    # Act
    actual = has_inline_marker(line, "@ts-ignore")

    # Assert
    assert actual is False


def test_has_inline_marker_recognizes_block_comment() -> None:
    # Arrange
    line = "items.push(v) /* @ts-ignore */"

    # Act
    actual = has_inline_marker(line, "@ts-ignore")

    # Assert
    assert actual is True


def test_has_top_of_file_marker_finds_directive(faker: Faker) -> None:
    # Arrange
    lines = ["", "// @ts-nocheck", f"const {faker.word()} = 1;"]

    # Act
    actual = has_top_of_file_marker(lines, "@ts-nocheck")

    # Assert
    assert actual is True


def test_has_top_of_file_marker_skips_past_scan_limit(faker: Faker) -> None:
    # Arrange
    lines = [f"// {faker.word()}" for _ in range(12)] + ["// @ts-nocheck"]

    # Act
    actual = has_top_of_file_marker(lines, "@ts-nocheck")

    # Assert
    assert actual is False


@pytest.mark.parametrize(
    ("lines", "expected"),
    [(["// @ts-nocheck", "code()"], True), (["code()"], False)],
)
def test_has_ts_nocheck_directive_alias_matches(
    lines: list[str], expected: bool
) -> None:
    # Arrange
    source_lines = list(lines)

    # Act
    result = has_ts_nocheck_directive(source_lines)

    # Assert
    assert result is expected


def test_has_python_file_disable_recognizes_mypy() -> None:
    # Arrange
    lines = ["# mypy: ignore-errors", "def f(): ..."]

    # Act
    result = has_python_file_disable(lines)

    # Assert
    assert result is True


def test_has_python_file_disable_recognizes_ruff() -> None:
    # Arrange
    lines = ["# ruff: noqa", "def f(): ..."]

    # Act
    result = has_python_file_disable(lines)

    # Assert
    assert result is True


def test_has_python_file_disable_absent(faker: Faker) -> None:
    # Arrange
    lines = [f"def {faker.word()}(): ...", "    pass"]

    # Act
    result = has_python_file_disable(lines)

    # Assert
    assert result is False


def test_line_or_prev_has_suppression_honors_a_next_line_directive() -> None:
    # Arrange
    lines = ["// eslint-disable-next-line", "items.push(v)"]

    # Act
    via_alias = line_or_prev_has_suppression(lines, 1)

    # Assert
    assert via_alias is True


def test_our_own_allow_marker_does_not_suppress() -> None:
    # Arrange
    lines = ["arr.push(v) // @allow-mutation -- ok"]

    # Act
    result = line_or_prev_has_suppression(lines, 0)

    # Assert
    assert result is False


def test_third_party_directive_still_suppresses() -> None:
    # Arrange
    lines = ["arr.push(v) // eslint-disable-line"]

    # Act
    result = line_or_prev_has_suppression(lines, 0)

    # Assert
    assert result is True


@pytest.mark.parametrize("index", [-1, 5])
def test_is_suppressed_out_of_range_returns_false(index: int) -> None:
    # Arrange
    lines = ["arr.push(v)"]

    # Act
    result = is_suppressed(lines, index)

    # Assert
    assert result is False


def test_block_state_open_without_close_extends_to_end() -> None:
    # Arrange
    lines = ["/* eslint-disable */", "a", "b"]

    # Act
    state = compute_block_state(lines)

    # Assert
    assert state.disabled_lines == frozenset({0, 1, 2})


def test_python_marker_on_preceding_line_suppresses() -> None:
    # Arrange
    lines = ["arr.append(x)  # noqa", "y = 1"]

    # Act
    actual = is_suppressed(lines, 1)

    # Assert
    assert actual is True
