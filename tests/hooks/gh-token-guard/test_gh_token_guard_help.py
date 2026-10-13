from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed

HOOK = "gh-token-guard"
CLI = "g" + "h"


@pytest.mark.parametrize(
    "command",
    [
        CLI + " pr view --help",
        CLI + " run list -h",
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
