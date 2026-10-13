from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "glab-token-guard"
CLI = "gl" + "ab"


@pytest.mark.parametrize(
    "command",
    [
        CLI + " mr view --help",
        CLI + " mr list -h",
        CLI + " api --help",
    ],
)
def test_a_help_request_needs_no_token(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_help_flag_after_a_value_does_not_exempt_a_real_call(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": CLI + " mr note 1 -m --help"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_reading_the_stored_token_for_the_call_needs_no_token(tool_use, run_hook):
    # Arrange
    command = (
        "GITLAB_TOKEN=$("
        + CLI
        + " config get token --host gitlab.com) "
        + CLI
        + " api projects/1/merge_requests"
    )
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
