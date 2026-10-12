from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "review-state-guard"


def test_blocks_request_changes(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr review 123 --event REQUEST_CHANGES --body 'please fix'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "REQUEST_CHANGES")


def test_blocks_dismiss_via_pr_review(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr review 123 --event DISMISS --body 'dismissing'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "DISMISS")


def test_blocks_dismiss_via_api(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh api repos/owner/repo/pulls/1/reviews/42/dismissals -X POST"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "DISMISS")


def test_blocks_delete_review(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh api -X DELETE repos/owner/repo/pulls/1/reviews/42"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "DELETE")


def test_blocks_delete_review_method_flag(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh api --method DELETE repos/owner/repo/pulls/1/reviews/42"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "DELETE")


def test_allows_comment_event(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr review 123 --event COMMENT --body 'looking good'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_approve_event(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr review 123 --event APPROVE"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_pr_view(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr view 123 --json reviews"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_bypass_env(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr review 123 --event REQUEST_CHANGES --body 'please fix'"},
    )

    # Act
    result = run_hook(HOOK, payload, env={"REVIEW_STATE_GUARD_DISABLE": "1"})

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
