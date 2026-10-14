from __future__ import annotations
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _todo_marker_blocker_helpers import HOOK


def test_line_allow_marker_does_not_suppress(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/doc-example.ts",
            "content": "// TODO: example -- allow-todo -- documents the pattern\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "TODO")


def test_file_allow_marker_does_not_suppress(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/doc-example.ts",
            "content": (
                "// @allow-todo -- this file documents the patterns\n"
                "// TODO: example 1\n"
                "// TODO: example 2\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "TODO")


def test_suppression_without_justification_does_not_allow(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// TODO: x // allow-todo\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "TODO")


def test_file_marker_only_in_first_ten_lines(tool_use, run_hook):
    # Arrange
    leading = "\n".join([f"// line {i}" for i in range(15)])
    trailing = "\n".join([f"// post {i}" for i in range(5)])
    content = (
        leading
        + "\n// @allow-todo -- after ten lines is too late\n"
        + trailing
        + "\n// TODO: hit\n"
    )
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": content,
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "TODO")


def test_file_allow_marker_after_blank_lines_does_not_suppress(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": ("\n\n\n// @allow-todo -- doc example file\n// TODO: example\n"),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "TODO")


def test_allow_marker_on_previous_line_does_not_suppress(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": (
                "// allow-todo -- this is a documented example\n"
                "// TODO: documented example\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "TODO")


def test_eslint_directive_still_suppresses(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// eslint-disable-next-line\n// TODO: documented example\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_eslint_disable_suppresses(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// eslint-disable-next-line\n// TODO: covered by eslint-disable\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
