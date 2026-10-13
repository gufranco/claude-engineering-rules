from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "gh-run-watch-blocker"


@pytest.mark.parametrize(
    "cmd",
    [
        "gh run watch",
        "gh run watch 12345",
        "gh run watch --exit-status",
        "GH_TOKEN=xxx gh run watch 99",
        "gh pr checks --watch",
        "gh pr checks 42 --watch",
        "gh pr checks -w",
        "gh workflow run ci.yml --watch",
        "glab ci view --live",
        "glab ci view 123 -l",
    ],
)
def test_blocks_polling_commands(tool_use, run_hook, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "polls every 3 seconds")


def test_blocks_in_compound_command(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git push && gh run watch"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "BLOCKED: `gh run watch` polls every 3 seconds and burns the GitHub API rate budget",
    )


@pytest.mark.parametrize(
    "cmd",
    [
        "gh run view 12345",
        "gh run view 12345 --log-failed",
        "gh run list",
        "gh pr checks 42",
        "gh pr view 42",
        "gh api rate_limit",
        "gh workflow run ci.yml",
        "glab ci view 123",
        "glab ci view 123 --output json",
    ],
)
def test_allows_one_shot_commands(tool_use, run_hook, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "cmd",
    [
        "git status",
        "ls -la",
        "watch ls",
        "grep watch readme.md",
    ],
)
def test_allows_unrelated(tool_use, run_hook, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize("tool_name", ["Write", "Edit", "Read", "Grep"])
def test_allows_unrelated_tools(tool_use, run_hook, tool_name):
    # Arrange
    payload = tool_use(tool_name, {"file_path": "/tmp/x"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_bypass_env_var_disables_check(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "gh run watch"})

    # Act
    result = run_hook(HOOK, payload, env={"GH_RUN_WATCH_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_handles_empty_command(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_handles_missing_tool_input(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash")

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
