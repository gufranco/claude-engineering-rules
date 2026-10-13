from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed

HOOK = "force-push-during-review"


def test_allows_non_force_push(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git push origin main"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_force_push_outside_a_repository(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Bash", {"command": "git push --force-with-lease"}, cwd=str(tmp_path)
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_force_push_with_bypass_env(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git push --force origin feature"})

    # Act
    result = run_hook(HOOK, payload, env={"FORCE_PUSH_DURING_REVIEW_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_allows_short_dash_f_force_outside_a_repository(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Bash", {"command": "git push -f origin feature"}, cwd=str(tmp_path)
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_force_refspec_outside_a_repository(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Bash", {"command": "git push origin +feature:main"}, cwd=str(tmp_path)
    )

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


def test_allows_git_pull(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git pull origin main"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "force-push-during-review.py"
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
    assert proc.returncode == 2
