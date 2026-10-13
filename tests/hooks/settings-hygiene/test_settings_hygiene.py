from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "settings-hygiene"


def test_blocks_inline_credentials(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/settings.json",
            "content": '{"db": "postgresql://user:secret123@host/x"}',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result, "BLOCKED: settings.json contains project- or machine-specific data."
    )


def test_the_block_report_never_echoes_the_password(tool_use, run_hook):
    # Arrange
    literal = "Pa55" + "w0rdLongEnough"
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/settings.json",
            "content": f'{{"db": "postgresql://user:{literal}@host/x"}}',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "postgresql://user:****@host/x")
    assert literal not in stderr


def test_blocks_absolute_home_path(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/settings.json",
            "content": '{"path": "/Users/alice/work/repo"}',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result, "BLOCKED: settings.json contains project- or machine-specific data."
    )


def test_allows_env_var_password(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/settings.json",
            "content": '{"db": "postgresql://user:${PASSWORD}@host/x"}',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_tilde_path(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/settings.json",
            "content": '{"path": "~/.claude/scripts"}',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_non_settings_file(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": '{"db": "postgresql://user:literal@host/x"}',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_clean_settings(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/settings.json",
            "content": '{"model": "claude-opus-4-7"}',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_on_edit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/settings.json",
            "old_string": "old",
            "new_string": '{"path": "/Users/bob/x"}',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result, "BLOCKED: settings.json contains project- or machine-specific data."
    )


def test_blocks_on_multiedit(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result, "BLOCKED: settings.json contains project- or machine-specific data."
    )


def test_disable_env_bypasses(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/settings.json",
            "content": '{"path": "/Users/x/repo"}',
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"SETTINGS_HYGIENE_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "settings-hygiene.py"
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


def test_no_file_path_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": "", "content": "{}"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
