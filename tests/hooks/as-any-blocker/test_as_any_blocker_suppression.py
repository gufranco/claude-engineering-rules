from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked


HOOK = "as-any-blocker"


def test_allows_in_single_line_comment(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": "// const x: any = 1; legacy\nconst x: number = 1;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_in_block_comment_line(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": "/* example: const x: any = 1; */\nconst x: number = 1;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_line_with_eslint_disable_line(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": "const x = value as any; // eslint-disable-line\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_line_with_ts_expect_error_above(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": "// @ts-expect-error legacy API\nconst x = value as any;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_inline_allow_marker_does_not_suppress(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": ("const x = value as any; // allow-any -- legacy type\n"),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "any")


def test_preceding_line_allow_marker_does_not_suppress(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": ("// allow-any -- third-party shim\nconst x = value as any;\n"),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "any")


def test_top_of_file_allow_marker_does_not_suppress(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": (
                "// @allow-any -- legacy file pending refactor\n"
                "const x = value as any;\n"
                "const y: any[] = [];\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "any")


def test_ts_expect_error_directive_still_suppresses(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": ("// @ts-expect-error\nconst x = value as any;\n"),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_when_marker_missing_justification(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": "const x = value as any; // allow-any\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "any` type detected")


def test_blocks_eslint_disable_block(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": (
                "/* eslint-disable */\nconst x = value as any;\n/* eslint-enable */\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_directive_for_another_rule_does_not_hide_any(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.ts",
            "content": "// eslint-disable-next-line no-console\nconst x = value as any;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "any` type detected")


def test_a_directive_naming_no_explicit_any_is_honored(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.ts",
            "content": (
                "// eslint-disable-next-line @typescript-eslint/no-explicit-any\n"
                "const x = value as any;\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
