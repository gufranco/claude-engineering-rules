from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "glab-token-guard"


def test_blocks_glab_mr_without_token(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "glab mr list"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "BLOCKED: glab command without explicit GITLAB_TOKEN.")


def test_blocks_glab_auth_login(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "glab auth login --hostname gitlab.com"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "BLOCKED: glab auth login changes the global config and affects all terminals.",
    )


def test_allows_glab_with_inline_token(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "GITLAB_TOKEN=abc glab mr list"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_glab_with_exported_token(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "export GITLAB_TOKEN=abc && glab mr list"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_glab_auth_status(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "glab auth status"})

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


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "glab-token-guard.py"
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    env["CLAUDE_BYPASS_STATE"] = os.devnull

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
