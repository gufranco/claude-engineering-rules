from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_blocked

HOOK = "ai-slop-blocker"
HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"
SLOP = "The cache " + "serves as a" + " buffer"


def _load_module():
    spec = importlib.util.spec_from_file_location("_asb_git_options", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "command",
    [
        "git -C /tmp/x commit -m 'fix: y'",
        "git -c core.editor=true commit -m 'fix: y'",
        "git --no-pager tag -a v1 -m 'v1'",
    ],
)
def test_git_message_behind_global_options_is_publishing(command):
    # Arrange
    module = _load_module()

    # Act
    publishing = module.is_publishing_bash(command)

    # Assert
    assert publishing is True


def test_git_status_behind_global_options_is_not_publishing():
    # Arrange
    module = _load_module()

    # Act
    publishing = module.is_publishing_bash("git -C /tmp/x status")

    # Assert
    assert publishing is False


def test_commit_behind_inline_config_with_slop_is_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": f"git -c a=b commit -m '{SLOP}'"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "SLOP006")
