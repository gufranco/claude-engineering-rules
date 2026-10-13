from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed, assert_blocked


HOOK = "as-any-blocker"


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
    assert_blocked(
        result,
        "Blocked: as-any-blocker could not read its input: tool_input.content is not a string.",
    )


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
    assert_blocked(
        result,
        "Blocked: as-any-blocker could not read its input: tool_input.new_string is not a string.",
    )


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
    assert_blocked(
        result,
        "Blocked: as-any-blocker could not read its input: tool_input.edits is not a list of",
    )


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
    assert_blocked(
        result,
        "Blocked: as-any-blocker could not read its input: tool_input.edits is not a list of",
    )


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
    env["CLAUDE_BYPASS_STATE"] = os.devnull

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
    assert "could not read its input" in proc.stderr
