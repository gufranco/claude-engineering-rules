from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
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


def test_disable_env_bypasses(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": "const x: any = 1;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"AS_ANY_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_disable_env_other_value_does_not_bypass(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": "const x: any = 1;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"AS_ANY_DISABLE": "0"})

    # Assert
    assert_blocked(result, "any` type detected")


def test_unknown_tool_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/src/x.ts"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_non_string_content_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/x.ts", "content": 12345},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_edit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/x.ts",
            "old_string": "a",
            "new_string": 999,
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_multiedit_non_dict_items_block(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/x.ts",
            "edits": ["not a dict", None, 42],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_multiedit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/x.ts",
            "edits": [{"old_string": "a", "new_string": 12345}],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_empty_file_path_is_skipped(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "const x: any = 1;\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_many_hits_truncates_listing(tool_use, run_hook):
    # Arrange
    lines = "\n".join(f"const v{i}: any = {i};" for i in range(12))
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/x.ts", "content": lines + "\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "more")


def test_tsx_file_is_scanned(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/Component.tsx",
            "content": "const props: any = useProps();\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "any` type detected")


def test_mts_file_is_scanned(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/module.mts",
            "content": "export const x: any = 1;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "any` type detected")


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "as-any-blocker.py"
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not valid json",
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )

    # Assert
    assert proc.returncode == 2


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
