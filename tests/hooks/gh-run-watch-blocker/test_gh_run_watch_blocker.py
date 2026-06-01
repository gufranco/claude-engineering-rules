"""Coverage for the gh-run-watch-blocker hook.

Source rule: rules/git-workflow.md CI/CD Monitoring section.
"""

from __future__ import annotations

import pytest

HOOK = "gh-run-watch-blocker"


# ---------------------------------------------------------------------------
# Block: polling commands
# ---------------------------------------------------------------------------


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
def test_blocks_polling_commands(tool_use, assert_blocks, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_blocks(HOOK, payload, "polls every 3 seconds")


def test_blocks_in_compound_command(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Bash", {"command": "git push && gh run watch"})

    # Act / Assert
    assert_blocks(HOOK, payload)


# ---------------------------------------------------------------------------
# Allow: one-shot gh commands
# ---------------------------------------------------------------------------


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
def test_allows_one_shot_commands(tool_use, assert_allows, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Allow: unrelated commands
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        "git status",
        "ls -la",
        "watch ls",  # `watch` builtin, not gh
        "grep watch readme.md",
    ],
)
def test_allows_unrelated(tool_use, assert_allows, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Allow: unrelated tools
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool_name", ["Write", "Edit", "Read", "Grep"])
def test_allows_unrelated_tools(tool_use, assert_allows, tool_name):
    # Arrange
    payload = tool_use(tool_name, {"file_path": "/tmp/x"})

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Bypass + robustness
# ---------------------------------------------------------------------------


def test_bypass_env_var_disables_check(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "gh run watch"})

    # Act / Assert
    assert_allows(HOOK, payload, env={"GH_RUN_WATCH_DISABLE": "1"})


def test_handles_empty_command(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_handles_missing_tool_input(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash")

    # Act / Assert
    assert_allows(HOOK, payload)
