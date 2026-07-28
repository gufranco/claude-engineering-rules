"""Coverage for terraform-workspace-guard hook."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "terraform-workspace-guard"


def test_blocks_workspace_select(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "terraform workspace select staging"})

    assert_blocks(HOOK, payload)


def test_blocks_workspace_new(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "terraform workspace new prod"})

    assert_blocks(HOOK, payload)


def test_allows_workspace_select_help(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "terraform workspace select --help"})

    assert_allows(HOOK, payload)


def test_allows_workspace_with_env_var(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "TF_WORKSPACE=staging terraform plan"})

    assert_allows(HOOK, payload)


def test_allows_workspace_list(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "terraform workspace list"})

    assert_allows(HOOK, payload)


def test_allows_unrelated_command(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "ls"})

    assert_allows(HOOK, payload)


def test_allows_empty_command(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": ""})

    assert_allows(HOOK, payload)


def test_invalid_json_stdin_does_not_crash():
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "terraform-workspace-guard.py"
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
