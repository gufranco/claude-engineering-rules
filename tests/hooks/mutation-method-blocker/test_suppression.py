"""Suppression marker coverage.

Item 124 of the plan. Validates ESLint and TypeScript markers
(eslint-disable-next-line, eslint-disable-line, eslint-disable block,
@ts-expect-error, @ts-ignore) and the hook-specific
`claude-allow-mutation` markers (per-line and top-of-file).

Also validates the justification trailer requirement: the hook-specific
markers without a `-- <reason>` trailer do NOT bypass the hook.
"""

from __future__ import annotations

import pytest

from conftest import make_write_payload


def test_eslint_disable_next_line_suppresses(run_hook):
    # Arrange
    snippet = """// eslint-disable-next-line
items.push(value)
"""
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr


def test_eslint_disable_line_suppresses(run_hook):
    # Arrange
    snippet = "items.push(value) // eslint-disable-line\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr


def test_eslint_disable_block_suppresses(run_hook):
    # Arrange
    snippet = """/* eslint-disable */
items.push(value)
items.sort()
items.reverse()
/* eslint-enable */
"""
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr


def test_ts_expect_error_preceding_line_suppresses(run_hook):
    # Arrange
    snippet = """// @ts-expect-error -- pre-existing legacy
items.push(value)
"""
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr


def test_ts_ignore_same_line_suppresses(run_hook):
    # Arrange
    snippet = "items.push(value) // @ts-ignore\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr


def test_claude_allow_mutation_per_line_with_trailer(run_hook):
    # Arrange
    snippet = "items.push(value) // claude-allow-mutation -- legacy callback API\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr


def test_claude_allow_mutation_preceding_line_with_trailer(run_hook):
    # Arrange
    snippet = """// claude-allow-mutation -- legacy callback
items.push(value)
"""
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr


def test_claude_allow_mutation_without_trailer_does_not_suppress(run_hook):
    # Arrange
    snippet = "items.push(value) // claude-allow-mutation\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, "marker without trailer must still block"
    assert "array.push" in stderr


def test_claude_allow_file_marker_with_trailer(run_hook):
    # Arrange
    snippet = """// @claude-allow-mutation -- legacy migration shim
items.push(value)
items.sort()
arr.splice(0, 1)
"""
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr


def test_claude_allow_file_marker_without_trailer_does_not_suppress(run_hook):
    # Arrange
    snippet = """// @claude-allow-mutation
items.push(value)
"""
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "array.push" in stderr


def test_claude_allow_file_marker_too_far_from_top_does_not_suppress(run_hook):
    # Arrange
    snippet = (
        "\n".join(["// padding"] * 12)
        + "\n// @claude-allow-mutation -- too late\nitems.push(value)\n"
    )
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "array.push" in stderr


def test_claude_allow_marker_inside_string_literal_does_not_suppress(run_hook):
    # Arrange
    snippet = "log('claude-allow-mutation -- not a real marker')\nitems.push(value)\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "array.push" in stderr


@pytest.mark.parametrize(
    "marker",
    ["// eslint-disable-line", "// @ts-expect-error", "// @ts-ignore"],
)
def test_standard_markers_each_suppress_independently(run_hook, marker):
    # Arrange
    snippet = f"items.push(value) {marker}\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"{marker}: unexpected block\n{stderr}"
