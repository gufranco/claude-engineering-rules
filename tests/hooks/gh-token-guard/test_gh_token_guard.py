"""Coverage for gh-token-guard hook.

Source rule: standards/multi-account-cli.md.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "gh-token-guard"


def test_blocks_gh_pr_without_token(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Bash", {"command": "gh pr list"})

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_gh_auth_switch(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Bash", {"command": "gh auth switch --user alice"})

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_allows_gh_with_inline_token(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash", {"command": "GH_TOKEN=$(gh auth token --user gufranco) gh pr list"}
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_gh_with_exported_token(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "export GH_TOKEN=abc && gh pr list"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_gh_auth_status(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "gh auth status"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_gh_auth_token(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "gh auth token --user me"})

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
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "gh-token-guard.py"
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
