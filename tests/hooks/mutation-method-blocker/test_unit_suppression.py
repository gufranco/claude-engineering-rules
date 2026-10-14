from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "hooks"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import suppression as supp  # noqa: E402


def test_suppression_lone_block_disable_recognized():
    # Arrange
    lines = ["// eslint-disable", "items.push(x);", "items.pop();", "// eslint-enable"]

    # Act
    state = supp.compute_block_state(lines)

    # Assert
    assert 0 in state.disabled_lines
    assert 1 in state.disabled_lines
    assert 2 in state.disabled_lines


def test_suppression_top_of_file_marker_blank_skip():
    # Arrange
    lines = ["", "", "// @ts-nocheck", "items.push(x);"]

    # Act
    result = supp.has_top_of_file_marker(lines, "@ts-nocheck")

    # Assert
    assert result is True


def test_suppression_top_of_file_marker_scan_limit():
    # Arrange
    lines = [f"const x{i} = 1;" for i in range(15)] + ["// @ts-nocheck"]

    # Act
    result = supp.has_top_of_file_marker(lines, "@ts-nocheck")

    # Assert
    assert result is False


def test_suppression_top_of_file_marker_empty_marker():
    # Arrange
    lines = ["// foo"]

    # Act
    result = supp.has_top_of_file_marker(lines, "")

    # Assert
    assert result is False


def test_suppression_is_suppressed_invalid_index_high():
    # Arrange
    lines = ["a", "b"]

    # Act
    result = supp.is_suppressed(lines, 5)

    # Assert
    assert result is False


def test_suppression_is_suppressed_negative_index():
    # Arrange
    lines = ["a", "b"]

    # Act
    result = supp.is_suppressed(lines, -1)

    # Assert
    assert result is False


def test_suppression_is_suppressed_block_state_none_computes():
    # Arrange
    lines = ["/* eslint-disable */", "items.push(x);", "/* eslint-enable */"]

    # Act
    result = supp.is_suppressed(lines, 1, block_state=None)

    # Assert
    assert result is True


def test_suppression_ignores_our_own_allow_marker():
    # Arrange
    lines = ["items.push(x); // allow-mutation -- justified"]

    # Act
    result = supp.is_suppressed(lines, 0)

    # Assert
    assert result is False


def test_suppression_strip_strings_backslash():
    # Arrange
    line = 'const s = "a\\"b";'

    # Act
    result = supp._strip_strings(line)

    # Assert
    assert len(result) == len(line)
    assert "a" not in result.split('"')[1]


def test_suppression_has_inline_marker_outside_comment():
    # Arrange
    line = 'const s = "@ts-ignore comment-like";'

    # Act
    result = supp.has_inline_marker(line, "@ts-ignore")

    # Assert
    assert result is False


def test_suppression_has_inline_marker_in_block_comment():
    # Arrange
    line = "/* @ts-ignore */ items.push(x);"

    # Act
    result = supp.has_inline_marker(line, "@ts-ignore")

    # Assert
    assert result is True


def test_suppression_preceding_disable_next_line():
    # Arrange
    lines = ["// eslint-disable-next-line", "items.push(x);"]

    # Act
    result = supp.is_suppressed(lines, 1)

    # Assert
    assert result is True


def test_suppression_lone_block_disable_helper_non_comment():
    # Arrange
    line = "items.push(x);"

    # Act
    result = supp._is_lone_block_disable(line)

    # Assert
    assert result is False


def test_suppression_lone_block_disable_with_eslint_disable():
    # Arrange
    line = "// eslint-disable"

    # Act
    result = supp._is_lone_block_disable(line)

    # Assert
    assert result is True


def test_suppression_has_ts_nocheck_directive_present():
    # Arrange
    lines = ["// @ts-nocheck", "items.push(x);"]

    # Act
    result = supp.has_ts_nocheck_directive(lines)

    # Assert
    assert result is True


def test_suppression_has_ts_nocheck_directive_with_blank_lines():
    # Arrange
    lines = ["", "", "// @ts-nocheck", "code();"]

    # Act
    result = supp.has_ts_nocheck_directive(lines)

    # Assert
    assert result is True


def test_suppression_has_ts_nocheck_directive_absent():
    # Arrange
    lines = ["// regular comment", "items.push(x);"]

    # Act
    result = supp.has_ts_nocheck_directive(lines)

    # Assert
    assert result is False


def test_suppression_has_ts_nocheck_directive_past_scan_limit():
    # Arrange
    lines = [f"// filler {i}" for i in range(15)] + ["// @ts-nocheck"]

    # Act
    result = supp.has_ts_nocheck_directive(lines)

    # Assert
    assert result is False
