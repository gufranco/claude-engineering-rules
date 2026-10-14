from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "gh-short-sha-guard"
FULL_SHA = "fd76b21c3e9a4b5d6f7081928374655647382910"


@pytest.mark.parametrize(
    "cmd",
    [
        "gh run list --commit fd76b21",
        "gh run list --commit=fd76b21",
        "gh run list -c fd76b21 --json status",
        'gh run list --commit "fd76b21" --json databaseId',
        "GH_TOKEN=x gh run list -L 3 --commit fd76b21c3e9a4b5d6f70819283746556473829",
        "cd repo && gh run list --commit fd76b21 --json status --jq length",
    ],
)
def test_blocks_short_sha_commit_filter(tool_use, run_hook, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "matches only the full 40-character SHA")


def test_block_names_the_rev_parse_fix(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "gh run list --commit abc1234"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, 'gh run list --commit "$(git rev-parse abc1234)"')


@pytest.mark.parametrize(
    "cmd",
    [
        f"gh run list --commit {FULL_SHA}",
        f'gh run list --commit "{FULL_SHA}" --json status',
        'gh run list --commit "$(git rev-parse fd76b21)"',
        'gh run list --commit "$sha"',
        "gh run list -L 5 --json databaseId,headSha",
        "gh run view 38610563397",
        "git log -c fd76b21",
        "gh pr list && git show fd76b21",
    ],
)
def test_allows_full_sha_and_unrelated_commands(tool_use, run_hook, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_disable_env_allows_short_sha(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "gh run list --commit abc1234"})

    # Act
    result = run_hook(HOOK, payload, env={"GH_SHORT_SHA_GUARD_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_allows_empty_command(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_ignores_non_bash_tools(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/tmp/x", "content": "gh run list --commit abc1234"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
