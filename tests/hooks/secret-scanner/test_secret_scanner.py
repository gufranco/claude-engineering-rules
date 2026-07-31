"""Coverage for secret-scanner hook.

The hook activates only on git commit commands. It scans staged files for
secret patterns; without staged files it exits cleanly.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "secret-scanner"


def test_allows_non_commit_bash_command(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "ls -la"})

    assert_allows(HOOK, payload)


def test_allows_git_log(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "git log --oneline -3"})

    assert_allows(HOOK, payload)


def test_allows_git_status(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "git status"})

    assert_allows(HOOK, payload)


def test_allows_empty_command(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": ""})

    assert_allows(HOOK, payload)


def test_allows_git_commit_outside_repo(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "git commit -m 'fix'"})

    assert_allows(HOOK, payload)


def test_invalid_json_stdin_does_not_crash():
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "secret-scanner.py"
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
