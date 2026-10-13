from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "aws-profile-guard"


@pytest.mark.parametrize(
    "command",
    [
        "aws configure set region us-east-1 && aws s3 ls --profile prod",
        "AWS_PROFILE=prod aws s3 ls; aws configure set region us-east-1",
    ],
)
def test_a_profile_on_another_call_does_not_cover_configure_set(
    tool_use, run_hook, command
):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "BLOCKED: `aws configure set ...` without `--profile <name>` writes to the default AWS",
    )


@pytest.mark.parametrize(
    "command",
    [
        "aws configure set region us-east-1 --profile prod",
        "aws configure set region us-east-1 --profile=prod",
        "AWS_PROFILE=prod aws configure set region us-east-1",
    ],
)
def test_configure_set_with_its_own_profile_passes(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
