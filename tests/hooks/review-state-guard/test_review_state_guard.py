"""Coverage for review-state-guard hook.

Source rule: skills/respond/SKILL.md, Rules section.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "review-state-guard"


def test_blocks_request_changes(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr review 123 --event REQUEST_CHANGES --body 'please fix'"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "REQUEST_CHANGES")


def test_blocks_dismiss_via_pr_review(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr review 123 --event DISMISS --body 'dismissing'"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "DISMISS")


def test_blocks_dismiss_via_api(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh api repos/owner/repo/pulls/1/reviews/42/dismissals -X POST"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "DISMISS")


def test_blocks_delete_review(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh api -X DELETE repos/owner/repo/pulls/1/reviews/42"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "DELETE")


def test_blocks_delete_review_method_flag(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh api --method DELETE repos/owner/repo/pulls/1/reviews/42"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "DELETE")


def test_allows_comment_event(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr review 123 --event COMMENT --body 'looking good'"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_approve_event(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr review 123 --event APPROVE"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_pr_view(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr view 123 --json reviews"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_bypass_env(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr review 123 --event REQUEST_CHANGES --body 'please fix'"},
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"REVIEW_STATE_GUARD_DISABLE": "1"})


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


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "review-state-guard.py"
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
