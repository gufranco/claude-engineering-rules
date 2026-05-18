"""Coverage for mise-global-guard hook."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "mise-global-guard"


def test_blocks_mise_use_global_long(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Bash", {"command": "mise use --global node@22"})

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_mise_use_global_short(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Bash", {"command": "mise use -g python@3.12"})

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_mise_unuse_global(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Bash", {"command": "mise unuse --global node"})

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_allows_mise_use_local(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "mise use node@22"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_mise_list(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "mise list"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_unrelated_command(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "ls"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_empty_command(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "mise-global-guard.py"
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
