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
    # Arrange
    payload = tool_use("Bash", {"command": "ls -la"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_git_log(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "git log --oneline -3"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_git_status(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "git status"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_empty_command(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_git_commit_outside_repo(tool_use, assert_allows):
    # Arrange
    # When git commit runs but `git diff --cached --name-only` fails or returns
    # nothing, the scanner finds no staged files and exits 0.
    payload = tool_use("Bash", {"command": "git commit -m 'fix'"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "secret-scanner.py"
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
