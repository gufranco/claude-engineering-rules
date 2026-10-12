from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "conventional-commits"


@pytest.mark.parametrize(
    "command",
    [
        "git -C /tmp/x commit -m 'updated stuff'",
        "git -C \"/tmp/my repo\" commit -m 'updated stuff'",
        "git -c core.editor=true commit -m 'updated stuff'",
        "git --git-dir=/x/.git commit -m 'updated stuff'",
    ],
)
def test_bad_subject_behind_global_options_is_blocked(command, tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "does not follow conventional commit format")


def test_good_subject_behind_global_options_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git -C /tmp/x commit -m 'fix: handle y'"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
