"""Coverage for git-author-guard hook.

Source rule: standards/git-identity.md.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "git-author-guard"


def test_blocks_git_config_user_email_local(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "git config user.email test@x.com"})

    assert_blocks(HOOK, payload)


def test_blocks_git_config_user_name_local(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "git config user.name 'Tester'"})

    assert_blocks(HOOK, payload)


def test_allows_git_config_get(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "git config --get user.email"})

    assert_allows(HOOK, payload)


def test_allows_git_config_global_user_email(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "git config --global user.email me@x.com"})

    assert_allows(HOOK, payload)


def test_allows_git_status(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "git status"})

    assert_allows(HOOK, payload)


def test_allows_git_log(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "git log --oneline -3"})

    assert_allows(HOOK, payload)


def test_allows_unrelated_command(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "ls"})

    assert_allows(HOOK, payload)


def test_allows_empty_command(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": ""})

    assert_allows(HOOK, payload)


def test_disable_env_bypasses(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "git config user.email x@y.com"})

    assert_allows(HOOK, payload, env={"GIT_AUTHOR_GUARD_DISABLE": "1"})


def test_invalid_json_stdin_does_not_crash():
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "git-author-guard.py"
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
