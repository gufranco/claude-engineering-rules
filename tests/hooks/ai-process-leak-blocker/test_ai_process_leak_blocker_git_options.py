from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_blocked

HOOK = "ai-process-leak-blocker"
HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"
LEAK = "Phase " + "2 lands here"


def _load_module():
    spec = importlib.util.spec_from_file_location("_aplb_git_options", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "command",
    [
        "git -C /tmp/x commit -m 'fix: y'",
        'git -C "/tmp/my repo" commit -m "fix: y"',
        "git -c core.editor=true commit -m 'fix: y'",
        "git --git-dir=/x/.git tag -a v1 -m 'v1'",
    ],
)
def test_git_message_behind_global_options_is_in_scope(command):
    # Arrange
    module = _load_module()

    # Act
    in_scope = module.bash_command_in_scope(command)

    # Assert
    assert in_scope is True


def test_git_status_behind_global_options_is_out_of_scope():
    # Arrange
    module = _load_module()

    # Act
    in_scope = module.bash_command_in_scope("git -C /tmp/x status")

    # Assert
    assert in_scope is False


def test_commit_behind_dash_c_with_leak_is_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": f"git -C /tmp/x commit -m '{LEAK}'"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Phase-N language")
