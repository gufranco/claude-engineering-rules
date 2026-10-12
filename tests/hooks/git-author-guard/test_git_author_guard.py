from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "git-author-guard"


def test_blocks_git_config_user_email_local(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git config user.email test@x.com"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_blocks_git_config_user_name_local(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git config user.name 'Tester'"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_allows_git_config_get(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git config --get user.email"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_git_config_global_user_email(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git config --global user.email me@x.com"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_git_status(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git status"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_git_log(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git log --oneline -3"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_unrelated_command(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "ls"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_empty_command(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_disable_env_bypasses(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git config user.email x@y.com"})

    # Act
    result = run_hook(HOOK, payload, env={"GIT_AUTHOR_GUARD_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "git-author-guard.py"
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
    assert proc.returncode == 0
