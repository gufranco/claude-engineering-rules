"""Coverage for settings-hygiene hook."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "settings-hygiene"


def test_blocks_inline_credentials(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/settings.json",
            "content": '{"db": "postgresql://user:secret123@host/x"}',
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_absolute_home_path(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/settings.json",
            "content": '{"path": "/Users/alice/work/repo"}',
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_allows_env_var_password(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/settings.json",
            "content": '{"db": "postgresql://user:${PASSWORD}@host/x"}',
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_tilde_path(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/settings.json",
            "content": '{"path": "~/.claude/scripts"}',
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_non_settings_file(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": '{"db": "postgresql://user:literal@host/x"}',
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_clean_settings(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/settings.json",
            "content": '{"model": "claude-opus-4-7"}',
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_blocks_on_edit(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/settings.json",
            "old_string": "old",
            "new_string": '{"path": "/Users/bob/x"}',
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_on_multiedit(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/settings.json",
            "edits": [
                {"old_string": "a", "new_string": '{"path": "/Users/x/repo"}'},
            ],
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_disable_env_bypasses(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/settings.json",
            "content": '{"path": "/Users/x/repo"}',
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"SETTINGS_HYGIENE_DISABLE": "1"})


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "settings-hygiene.py"
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


def test_no_file_path_is_allowed(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Write", {"file_path": "", "content": "{}"})

    # Act / Assert
    assert_allows(HOOK, payload)
