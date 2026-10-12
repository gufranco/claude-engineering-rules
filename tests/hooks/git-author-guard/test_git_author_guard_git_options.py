from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "git-author-guard"


@pytest.mark.parametrize(
    "command",
    [
        "git -C /tmp/x config user.email dev@x.test",
        'git -C "/tmp/my repo" config user.name Dev',
        "git -c core.x=y config user.email dev@x.test",
        "git --no-pager config --local user.email dev@x.test",
    ],
)
def test_local_identity_write_behind_global_options_is_blocked(
    command, tool_use, run_hook
):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "BLOCKED:")


def test_inline_identity_override_on_commit_behind_dash_c_is_blocked(
    tool_use, run_hook
):
    # Arrange
    command = 'git -C "/tmp/my repo" -c user.email=x@y.test commit -m "fix: y"'
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "inline `-c user.email=`")


def test_global_identity_write_behind_dash_c_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash", {"command": "git -C /tmp/x config --global user.email dev@x.test"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
