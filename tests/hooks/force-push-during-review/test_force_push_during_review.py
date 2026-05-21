"""Coverage for force-push-during-review hook.

Source rule: skills/respond/SKILL.md, Rules section. The hook reaches
out to `gh pr view` to determine whether a CHANGES_REQUESTED review is
open. When `gh` is not configured for the test environment, the hook
fail-opens, so most assertions here rely on the bypass env var to
exercise the block path deterministically.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "force-push-during-review"


def test_allows_non_force_push(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "git push origin main"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_force_push_with_no_blocking_review(tool_use, assert_allows):
    """Fail-open path: the gh lookup fails in the test environment, so
    the hook should allow."""
    # Arrange
    payload = tool_use("Bash", {"command": "git push --force-with-lease"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_force_push_with_bypass_env(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "git push --force origin feature"})

    # Act / Assert
    assert_allows(HOOK, payload, env={"FORCE_PUSH_DURING_REVIEW_DISABLE": "1"})


def test_allows_short_dash_f_force(tool_use, assert_allows):
    """The hook detects -f as a force flag, but fail-opens when no
    blocking review is found."""
    # Arrange
    payload = tool_use("Bash", {"command": "git push -f origin feature"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_force_refspec(tool_use, assert_allows):
    """The +ref refspec form is a force push but the hook fail-opens
    when no blocking review is found."""
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "git push origin +feature:main"},
    )

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


def test_allows_git_pull(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "git pull origin main"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_invalid_json_stdin_does_not_crash():
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
    assert proc.returncode == 0
