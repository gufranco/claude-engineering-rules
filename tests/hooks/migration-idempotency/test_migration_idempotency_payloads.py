from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from _helpers.hook_assertions import assert_allowed, assert_blocked
from _mig_support import (
    HOOK,
)


def test_write_non_string_content_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
            "content": 42,
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: migration-idempotency could not read its input: tool_input.content is not a",
    )


def test_edit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
            "old_string": "old",
            "new_string": 999,
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: migration-idempotency could not read its input: tool_input.new_string is not a",
    )


def test_multiedit_non_dict_edits_block(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
            "edits": ["nope", None, 42],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: migration-idempotency could not read its input: tool_input.edits is not a list",
    )


def test_multiedit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
            "edits": [{"old_string": "a", "new_string": 12345}],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: migration-idempotency could not read its input: tool_input.edits is not a list",
    )


def test_empty_file_path_is_safe(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "CREATE TABLE users (id uuid);\n"},
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
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
            "content": "CREATE TABLE users (id uuid); DROP TABLE users;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"MIGRATION_IDEMPOTENCY_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_disable_env_other_value_does_not_bypass(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
            "content": "CREATE TABLE users (id uuid);\n",
        },
    )

    # Act
    result = run_hook(
        HOOK,
        payload,
        env={
            "MIGRATION_IDEMPOTENCY_DISABLE": "0",
            "MIGRATION_ALLOW_BLOCKING_INDEX": "1",
        },
    )

    # Assert
    assert_blocked(result, "not idempotent")


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "migration-idempotency.py"
    )
    env = {**os.environ, "CLAUDE_HOOK_AUDIT_DISABLE": "1"}

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
