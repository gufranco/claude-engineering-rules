from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "kubectl-context-guard"


def test_blocks_kubectl_use_context(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "kubectl config use-context prod"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_blocks_kubectx_with_name(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "kubectx staging"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_blocks_kubectx_previous(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "kubectx -"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_allows_kubectx_list(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "kubectx"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_kubectl_with_context_flag(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "kubectl --context staging get pods"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_kubectl_use_context_help(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "kubectl config use-context --help"})

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
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "kubectl-context-guard.py"
    )
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
