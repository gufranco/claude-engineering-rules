"""Coverage for glab-token-guard hook.

Source rule: standards/multi-account-cli.md.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "glab-token-guard"


def test_blocks_glab_mr_without_token(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Bash", {"command": "glab mr list"})

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_glab_auth_login(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Bash", {"command": "glab auth login --hostname gitlab.com"})

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_allows_glab_with_inline_token(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "GITLAB_TOKEN=abc glab mr list"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_glab_with_exported_token(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "export GITLAB_TOKEN=abc && glab mr list"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_glab_auth_status(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "glab auth status"})

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
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "glab-token-guard.py"
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
