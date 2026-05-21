"""Coverage for as-any-blocker hook.

Source rule: `~/.claude/rules/code-style.md` "Strong typing".
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


HOOK = "as-any-blocker"


def test_blocks_as_any_assertion(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.ts",
            "content": "const x = value as any;\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "any` type detected")


def test_blocks_colon_any_annotation(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.ts",
            "content": "function f(arg: any) { return arg; }\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "any` type detected")


def test_blocks_generic_any(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.ts",
            "content": "const arr = parse<any>(data);\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "any` type detected")


def test_blocks_any_array(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.ts",
            "content": "const arr: any[] = [];\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "any` type detected")


def test_blocks_record_string_any(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.ts",
            "content": "const data: Record<string, any> = {};\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "any` type detected")


def test_blocks_on_edit(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/user.ts",
            "old_string": "old",
            "new_string": "const x = value as any;",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "any` type detected")


def test_blocks_on_multiedit(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "any` type detected")


def test_allows_clean_typescript(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.ts",
            "content": "const x: unknown = parse(input);\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_unknown_narrow(tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_d_ts_files(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/types.d.ts",
            "content": "declare const config: any;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_non_ts_files(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/script.py",
            "content": "x = 'this is not any TypeScript'\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_hooks_directory(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/gufranco/.claude/hooks/example.ts",
            "content": "const x: any = 1;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_in_single_line_comment(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": "// const x: any = 1; legacy\nconst x: number = 1;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_in_block_comment_line(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": "/* example: const x: any = 1; */\nconst x: number = 1;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_line_with_eslint_disable_line(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": "const x = value as any; // eslint-disable-line\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_line_with_ts_expect_error_above(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": "// @ts-expect-error legacy API\nconst x = value as any;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_line_with_inline_allow_marker(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": ("const x = value as any; // allow-any -- legacy type\n"),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_preceding_line_allow_marker(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": (
                "// allow-any -- third-party shim\nconst x = value as any;\n"
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_top_of_file_marker(tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_blocks_when_marker_missing_justification(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": "const x = value as any; // allow-any\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "any` type detected")


def test_blocks_eslint_disable_block(tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_disable_env_bypasses(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": "const x: any = 1;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"AS_ANY_DISABLE": "1"})


def test_disable_env_other_value_does_not_bypass(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.ts",
            "content": "const x: any = 1;\n",
        },
    )

    # Act / Assert
    assert_blocks(
        HOOK,
        payload,
        "any` type detected",
        env={"AS_ANY_DISABLE": "0"},
    )


def test_unknown_tool_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/src/x.ts"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_write_non_string_content_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/x.ts", "content": 12345},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_edit_non_string_new_string_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/x.ts",
            "old_string": "a",
            "new_string": 999,
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_non_dict_items_are_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/x.ts",
            "edits": ["not a dict", None, 42],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_non_string_new_string_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/x.ts",
            "edits": [{"old_string": "a", "new_string": 12345}],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_empty_file_path_is_skipped(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "const x: any = 1;\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_many_hits_truncates_listing(tool_use, assert_blocks):
    # Arrange
    lines = "\n".join(f"const v{i}: any = {i};" for i in range(12))
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/x.ts", "content": lines + "\n"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "more")


def test_tsx_file_is_scanned(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/Component.tsx",
            "content": "const props: any = useProps();\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "any` type detected")


def test_mts_file_is_scanned(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/module.mts",
            "content": "export const x: any = 1;\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "any` type detected")


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "as-any-blocker.py"
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    for k in ("COVERAGE_PROCESS_START", "PYTHONPATH"):
        if k in os.environ:
            env[k] = os.environ[k]

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
    assert proc.returncode == 0
