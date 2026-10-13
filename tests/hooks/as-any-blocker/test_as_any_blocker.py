from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked


HOOK = "as-any-blocker"


def test_blocks_as_any_assertion(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.ts",
            "content": "const x = value as any;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "any` type detected")


def test_blocks_colon_any_annotation(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.ts",
            "content": "function f(arg: any) { return arg; }\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "any` type detected")


def test_blocks_generic_any(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.ts",
            "content": "const arr = parse<any>(data);\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "any` type detected")


def test_blocks_any_array(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.ts",
            "content": "const arr: any[] = [];\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "any` type detected")


def test_blocks_record_string_any(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.ts",
            "content": "const data: Record<string, any> = {};\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "any` type detected")


def test_blocks_on_edit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/user.ts",
            "old_string": "old",
            "new_string": "const x = value as any;",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "any` type detected")


def test_blocks_on_multiedit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/user.ts",
            "edits": [
                {"old_string": "a", "new_string": "const x: any = 1;"},
                {"old_string": "b", "new_string": "const y = 2;"},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "any` type detected")


def test_allows_clean_typescript(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.ts",
            "content": "const x: unknown = parse(input);\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_unknown_narrow(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/parse.ts",
            "content": (
                "function parse(x: unknown): string {\n"
                "  if (typeof x === 'string') return x;\n"
                "  return '';\n"
                "}\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_d_ts_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/types.d.ts",
            "content": "declare const config: any;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_non_ts_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/script.py",
            "content": "x = 'this is not any TypeScript'\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_hooks_directory(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/gufranco/.claude/hooks/example.ts",
            "content": "const x: any = 1;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
