from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "aws-profile-guard"


def test_blocks_configure_set_without_profile(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "aws configure set region us-east-1"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_allows_configure_set_with_profile_flag(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "aws configure set --profile dev region us-east-1"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_configure_set_with_profile_env(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "AWS_PROFILE=staging aws configure set region us-east-1"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_unrelated_aws_command(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "aws s3 ls"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_unrelated_command(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "ls -la"})

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


def test_allows_configure_set_with_profile_equals(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "aws configure set --profile=prod region us-east-1"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "aws-profile-guard.py"
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
    assert proc.returncode == 0
