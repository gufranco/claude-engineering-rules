from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "gh-token-guard"
TOKEN = "GH_TOKEN=$(gh auth token --user acct)"


@pytest.mark.parametrize(
    "command",
    [
        f"{TOKEN} gh pr list && gh api user",
        f"{TOKEN} gh pr list; gh issue list",
        f"{TOKEN} gh pr list\ngh api user",
        f"gh api user && {TOKEN} gh pr list",
        "echo GH_TOKEN=x && gh api user",
    ],
)
def test_every_gh_call_needs_its_own_token(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "GH_TOKEN")


@pytest.mark.parametrize(
    "command",
    [
        f"{TOKEN} gh pr list && {TOKEN} gh api user",
        "export GH_TOKEN=$(gh auth token --user acct)\ngh pr list && gh api user",
        "export GH_TOKEN=$(gh auth token --user acct); gh api user",
        f"cd /tmp && {TOKEN} gh pr view 3 --json state",
        f"env {TOKEN} gh api user",
        "gh auth status && gh --version",
    ],
)
def test_calls_that_carry_or_inherit_a_token_pass(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_an_export_after_the_call_does_not_cover_it(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash", {"command": "gh api user && export GH_TOKEN=$(gh auth token --user a)"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "GH_TOKEN")


@pytest.mark.parametrize(
    "command",
    [
        'rg -n "user-attachments|gh release upload|pr-assets" docs',
        'grep -E "a;gh api user&&b" notes.txt',
    ],
)
def test_a_cli_name_inside_a_double_quoted_pattern_is_not_a_call(
    tool_use, run_hook, command
):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
