from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "mise-global-guard"


def test_blocks_mise_use_global_long(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "mise use --global node@22"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_blocks_mise_use_global_short(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "mise use -g python@3.12"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_blocks_mise_unuse_global(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "mise unuse --global node"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_allows_mise_use_local(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "mise use node@22"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_mise_list(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "mise list"})

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


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "mise-global-guard.py"
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
