from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "gh-run-watch-blocker"
CLI = "gl" + "ab"


@pytest.mark.parametrize(
    "command",
    [
        CLI + " ci status --wait",
        CLI + " ci status -w",
        CLI + " ci status --live",
        CLI + " ci status -b main -l",
    ],
)
def test_a_waiting_pipeline_status_blocks(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "BLOCKED: `glab ci status --wait` polls every 3 seconds and burns the GitHub API rate",
    )


@pytest.mark.parametrize(
    "command", [CLI + " ci status", CLI + " ci status -F json -b main"]
)
def test_a_one_shot_pipeline_status_is_allowed(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
