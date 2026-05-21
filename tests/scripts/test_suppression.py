"""Direct unit tests for `scripts/suppression.py`.

Spec: `specs/2026-05-09-claude-config-state-of-art/plan.md` 1.1.2.
Covers every honored suppression marker on multi-line, single-line,
escaped, and false-positive inputs. The hook-level integration tests in
`tests/hooks/mutation-method-blocker/test_suppression.py` exercise the
function through the mutation hook; this file exercises it in isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from suppression import (  # noqa: E402
    BlockState,
    compute_block_state,
    has_inline_marker,
    has_justification_trailer,
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
    assert 0 in state.disabled_lines
    assert 1 in state.disabled_lines
    assert 2 in state.disabled_lines
    assert 3 not in state.disabled_lines
    assert 4 not in state.disabled_lines


def test_block_state_dataclass_default_is_empty() -> None:
    # Arrange/Act
    state = BlockState()

    # Assert
    assert state.disabled_lines == frozenset()


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


def test_has_top_of_file_marker_finds_directive() -> None:
    # Arrange
    lines = ["", "// @ts-nocheck", "const x = 1;"]

    # Act
    actual = has_top_of_file_marker(lines, "@ts-nocheck")

    # Assert
    assert actual is True


def test_has_top_of_file_marker_skips_past_scan_limit() -> None:
    # Arrange
    lines = ["// line"] * 12 + ["// @ts-nocheck"]

    # Act
    actual = has_top_of_file_marker(lines, "@ts-nocheck")

    # Assert
    assert actual is False


def test_has_ts_nocheck_directive_alias_matches() -> None:
    # Arrange
    lines = ["// @ts-nocheck", "code()"]

    # Act/Assert
    assert has_ts_nocheck_directive(lines) is True
    assert has_ts_nocheck_directive(["code()"]) is False


def test_has_python_file_disable_recognizes_mypy() -> None:
    # Arrange
    lines = ["# mypy: ignore-errors", "def f(): ..."]

    # Act/Assert
    assert has_python_file_disable(lines) is True


def test_has_python_file_disable_recognizes_ruff() -> None:
    # Arrange
    lines = ["# ruff: noqa", "def f(): ..."]

    # Act/Assert
    assert has_python_file_disable(lines) is True


def test_has_python_file_disable_absent() -> None:
    # Arrange
    lines = ["def f(): ...", "    pass"]

    # Act/Assert
    assert has_python_file_disable(lines) is False


def test_has_justification_trailer_detects_reason() -> None:
    # Arrange/Act/Assert
    assert has_justification_trailer("// eslint-disable-line -- legacy code") is True
    assert has_justification_trailer("// eslint-disable-line") is False


def test_line_or_prev_has_suppression_alias_matches_is_suppressed() -> None:
    # Arrange
    lines = ["// eslint-disable-next-line", "items.push(v)"]

    # Act
    via_alias = line_or_prev_has_suppression(lines, 1)
    via_canonical = is_suppressed(lines, 1)

    # Assert
    assert via_alias is True
    assert via_alias == via_canonical


def test_line_or_prev_has_suppression_with_hook_marker() -> None:
    # Arrange
    lines = ["arr.push(v) // @allow-mutation -- ok"]

    # Act
    actual = line_or_prev_has_suppression(
        lines, 0, hook_marker="@allow-mutation"
    )

    # Assert
    assert actual is True


def test_is_suppressed_out_of_range_returns_false() -> None:
    # Arrange
    lines = ["arr.push(v)"]

    # Act/Assert
    assert is_suppressed(lines, -1) is False
    assert is_suppressed(lines, 5) is False


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
