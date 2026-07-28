"""Coverage for mise-global-guard hook."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "mise-global-guard"


def test_blocks_mise_use_global_long(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "mise use --global node@22"})

    assert_blocks(HOOK, payload)


def test_blocks_mise_use_global_short(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "mise use -g python@3.12"})

    assert_blocks(HOOK, payload)


def test_blocks_mise_unuse_global(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "mise unuse --global node"})

    assert_blocks(HOOK, payload)


def test_allows_mise_use_local(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "mise use node@22"})

    assert_allows(HOOK, payload)


def test_allows_mise_list(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "mise list"})

    assert_allows(HOOK, payload)


def test_allows_unrelated_command(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "ls"})

    assert_allows(HOOK, payload)


def test_allows_empty_command(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": ""})

    assert_allows(HOOK, payload)


def test_invalid_json_stdin_does_not_crash():
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "mise-global-guard.py"
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
