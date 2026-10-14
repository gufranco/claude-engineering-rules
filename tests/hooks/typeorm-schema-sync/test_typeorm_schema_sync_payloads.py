from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _typeorm_schema_sync_helpers import HOOK


def test_skips_test_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/__tests__/setup.ts",
            "content": "await dataSource.synchronize();\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_spec_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/user.spec.ts",
            "old_string": "old",
            "new_string": "synchronize: true",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_non_ts_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/notes.md",
            "content": "We had @Index(['col']) issues last quarter.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_disable_env_bypasses_block(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/data-source.ts",
            "content": "synchronize: true",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"TYPEORM_SCHEMA_SYNC_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_disable_env_other_value_does_not_bypass(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/data-source.ts",
            "content": "synchronize: true",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"TYPEORM_SCHEMA_SYNC_DISABLE": "0"})

    # Assert
    assert_blocked(result, "synchronize: true")


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "typeorm-schema-sync.py"
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


def test_payload_without_tool_input_is_allowed_silently(run_hook):
    # Arrange
    payload = {"_not": "a-valid-tool-payload"}

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert (result.code, result.stdout, result.stderr) == (0, "", "")


def test_empty_file_path_with_clean_content_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "const x = 1;\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_with_non_string_content_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/data-source.ts", "content": 12345},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: typeorm-schema-sync could not read its input: tool_input.content is not a",
    )


def test_multiedit_with_non_dict_items_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/data-source.ts",
            "edits": ["not a dict", None, 42],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: typeorm-schema-sync could not read its input: tool_input.edits is not a list",
    )


def test_edit_with_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/data-source.ts",
            "old_string": "old",
            "new_string": 12345,
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: typeorm-schema-sync could not read its input: tool_input.new_string is not a",
    )


def test_multiedit_with_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/data-source.ts",
            "edits": [{"old_string": "a", "new_string": 999}],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: typeorm-schema-sync could not read its input: tool_input.edits is not a list",
    )


def test_disable_audit_env_bypasses_branch(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/src/x.ts", "content": "synchronize: true"}
    )

    # Act
    result = run_hook(HOOK, payload, env={"TYPEORM_SCHEMA_SYNC_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_unknown_tool_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Read",
        {"file_path": "/repo/src/data-source.ts"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_multiedit_collects_findings(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/entities/order.entity.ts",
            "edits": [
                {"old_string": "x", "new_string": "@Index(['col'])"},
                {"old_string": "y", "new_string": "synchronize: true"},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Blocked")
