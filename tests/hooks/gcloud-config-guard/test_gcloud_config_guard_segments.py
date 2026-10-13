from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "gcloud-config-guard"


def test_a_configuration_flag_on_another_call_does_not_cover_config_set(
    tool_use, run_hook
):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gcloud --configuration=dev info && gcloud config set project p"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


@pytest.mark.parametrize(
    "command",
    [
        "gcloud config set project p --configuration=dev",
        "gcloud --configuration dev config set project p",
        "CLOUDSDK_ACTIVE_CONFIG_NAME=dev gcloud config set project p",
    ],
)
def test_config_set_with_its_own_configuration_passes(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
