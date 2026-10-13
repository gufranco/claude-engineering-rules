from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "terraform-workspace-guard"


def test_blocks_workspace_select(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "terraform workspace select staging"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_blocks_workspace_new(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "terraform workspace new prod"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_allows_workspace_select_help(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "terraform workspace select --help"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_workspace_with_env_var(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "TF_WORKSPACE=staging terraform plan"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_workspace_list(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "terraform workspace list"})

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


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "terraform-workspace-guard.py"
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
