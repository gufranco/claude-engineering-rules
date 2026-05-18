"""Coverage for docker-context-guard hook.

Source rule: standards/multi-account-cli.md.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "docker-context-guard"


def test_blocks_docker_context_use(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Bash", {"command": "docker context use staging"})

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_allows_docker_context_use_help(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "docker context use --help"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_docker_context_use_short_help(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "docker context use -h"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_per_command_context_flag(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "docker --context staging ps"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_docker_context_ls(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "docker context ls"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_unrelated_command(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "ls -la"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_empty_command(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "docker-context-guard.py"
    )
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
