from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "docker-context-guard"


def test_blocks_docker_context_use(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "docker context use staging"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_allows_docker_context_use_help(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "docker context use --help"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_docker_context_use_short_help(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "docker context use -h"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_per_command_context_flag(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "docker --context staging ps"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_docker_context_ls(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "docker context ls"})

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


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "docker-context-guard.py"
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
    assert proc.returncode == 0
