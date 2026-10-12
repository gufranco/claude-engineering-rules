from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_blocked

HOOK = "internal-config-leakage"
HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"
LEAK = "follow " + "rules/" + "testing.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("_icl_git_options", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GIT_MESSAGE_COMMANDS = [
    "git -C /tmp/x commit -m 'fix: y'",
    "git -c core.editor=true commit -m 'fix: y'",
    "git --git-dir /x/.git notes add -m 'n'",
]


@pytest.mark.parametrize("command", GIT_MESSAGE_COMMANDS)
def test_git_message_behind_global_options_is_publishing(command):
    # Arrange
    module = _load_module()

    # Act
    publishing = module.is_publishing_bash(command)

    # Assert
    assert publishing is True


@pytest.mark.parametrize("command", GIT_MESSAGE_COMMANDS)
def test_git_message_behind_global_options_is_a_git_message(command):
    # Arrange
    module = _load_module()

    # Act
    git_message = module.is_git_message_bash(command)

    # Assert
    assert git_message is True


def test_git_status_behind_global_options_is_not_publishing():
    # Arrange
    module = _load_module()

    # Act
    publishing = module.is_publishing_bash("git -C /tmp/x status")

    # Assert
    assert publishing is False


def test_commit_behind_dash_c_with_leak_is_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": f"git -C /tmp/x commit -m '{LEAK}'"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal markdown reference")
