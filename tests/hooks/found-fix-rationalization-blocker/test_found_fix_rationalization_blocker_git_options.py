from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_blocked

HOOK = "found-fix-rationalization-blocker"
HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"
DODGE = "orthogonal " + "to this task"


def _load_module():
    spec = importlib.util.spec_from_file_location("_ffrb_git_options", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "command",
    [
        "git -C /tmp/x commit -m 'fix: y'",
        "git -c core.editor=true commit -m 'fix: y'",
        "git -C /tmp/x tag -a v1 -m 'v1'",
        "git --no-pager notes add -m 'n'",
    ],
)
def test_git_message_behind_global_options_publishes(command):
    # Arrange
    module = _load_module()

    # Act
    publishes = module.bash_command_publishes(command)

    # Assert
    assert publishes is True


def test_git_status_behind_global_options_does_not_publish():
    # Arrange
    module = _load_module()

    # Act
    publishes = module.bash_command_publishes("git -C /tmp/x status")

    # Assert
    assert publishes is False


def test_commit_behind_dash_c_with_rationalization_is_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": f"git -C /tmp/x commit -m '{DODGE}'"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "orthogonal to this")
