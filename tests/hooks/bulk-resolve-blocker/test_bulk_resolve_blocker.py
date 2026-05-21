"""Coverage for bulk-resolve-blocker hook.

Source rule: skills/respond/SKILL.md, Resolution Convention section.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "bulk-resolve-blocker"


def test_blocks_github_loop_resolve(tool_use, assert_blocks):
    # Arrange
    cmd = (
        "for tid in PRRT_1 PRRT_2; do "
        "gh api graphql -f q='mutation { resolveReviewThread(input: { threadId: PRRT_X }) "
        "{ thread { id } } }'; done"
    )
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_blocks(HOOK, payload, "bulk resolution")


def test_blocks_gitlab_loop_resolve(tool_use, assert_blocks):
    # Arrange
    cmd = (
        "for d in D1 D2; do "
        "glab api -X PUT 'projects/foo/merge_requests/1/discussions/'$d "
        "--field resolved=true; done"
    )
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_blocks(HOOK, payload, "bulk resolution")


def test_blocks_multiple_github_resolves(tool_use, assert_blocks):
    # Arrange
    cmd = (
        "gh api graphql -f q='mutation { resolveReviewThread(input: { threadId: A }) "
        "{ thread { id } } }' && "
        "gh api graphql -f q='mutation { resolveReviewThread(input: { threadId: B }) "
        "{ thread { id } } }'"
    )
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_blocks(HOOK, payload, "bulk resolution")


def test_blocks_xargs_resolve(tool_use, assert_blocks):
    # Arrange
    cmd = (
        "echo PRRT_1 PRRT_2 | xargs -I{} "
        "gh api graphql -f q='mutation { resolveReviewThread(input: { threadId: {} }) "
        "{ thread { id } } }'"
    )
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_blocks(HOOK, payload, "bulk resolution")


def test_allows_single_github_resolve(tool_use, assert_allows):
    # Arrange
    cmd = (
        "gh api graphql -f q='mutation { resolveReviewThread(input: { threadId: PRRT_1 }) "
        "{ thread { id } } }'"
    )
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_single_gitlab_resolve(tool_use, assert_allows):
    # Arrange
    cmd = (
        "glab api -X PUT 'projects/foo/merge_requests/1/discussions/D1' "
        "--field resolved=true"
    )
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_loop_without_real_resolve_call(tool_use, assert_allows):
    """The hook used to false-positive whenever a loop coincided with a bare
    `resolveReviewThread` mention. Should now allow when no actual API call
    invokes the mutation."""
    # Arrange
    cmd = "for h in hook1 hook2 hook3; do echo $h; done; echo resolveReviewThread once"
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_bypass_env(tool_use, assert_allows):
    # Arrange
    cmd = (
        "for tid in PRRT_1 PRRT_2; do "
        "gh api graphql -f q='mutation { resolveReviewThread(input: { threadId: PRRT_X }) "
        "{ thread { id } } }'; done"
    )
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_allows(HOOK, payload, env={"BULK_RESOLVE_DISABLE": "1"})


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
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "bulk-resolve-blocker.py"
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
