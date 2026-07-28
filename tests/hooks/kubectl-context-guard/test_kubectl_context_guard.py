"""Coverage for kubectl-context-guard hook."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "kubectl-context-guard"


def test_blocks_kubectl_use_context(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "kubectl config use-context prod"})

    assert_blocks(HOOK, payload)


def test_blocks_kubectx_with_name(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "kubectx staging"})

    assert_blocks(HOOK, payload)


def test_blocks_kubectx_previous(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "kubectx -"})

    assert_blocks(HOOK, payload)


def test_allows_kubectx_list(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "kubectx"})

    assert_allows(HOOK, payload)


def test_allows_kubectl_with_context_flag(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "kubectl --context staging get pods"})

    assert_allows(HOOK, payload)


def test_allows_kubectl_use_context_help(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "kubectl config use-context --help"})

    assert_allows(HOOK, payload)


def test_allows_unrelated_command(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "ls"})

    assert_allows(HOOK, payload)


def test_allows_empty_command(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": ""})

    assert_allows(HOOK, payload)


def test_invalid_json_stdin_does_not_crash():
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "kubectl-context-guard.py"
    )
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    for k in ("COVERAGE_PROCESS_START", "PYTHONPATH"):
        if k in os.environ:
            env[k] = os.environ[k]

    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not valid json",
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )

    assert proc.returncode == 0
