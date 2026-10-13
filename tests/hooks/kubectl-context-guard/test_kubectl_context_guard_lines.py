from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_blocked

HOOK = "kubectl-context-guard"


@pytest.mark.parametrize(
    "command",
    ["ls\nkubectx prod", "ls\nkubectx -"],
)
def test_a_context_switch_on_a_later_line_is_blocked(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "BLOCKED: `kubectx <name>` calls `kubectl config use-context` and mutates the active",
    )
