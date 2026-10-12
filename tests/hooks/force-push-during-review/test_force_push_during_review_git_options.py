from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

HOOK = "force-push-during-review"
HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"
FORCE = "--" + "force"


def _load_module():
    spec = importlib.util.spec_from_file_location("_fpdr_git_options", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "command",
    [
        f"git -C /tmp/x push {FORCE} origin feat",
        f"git -c core.x=y push {FORCE}-with-lease",
        "git --git-dir=/x/.git push origin +feat",
        'git -C "/tmp/my repo" push origin +feat:main',
    ],
)
def test_force_push_behind_global_options_is_detected(command):
    # Arrange
    module = _load_module()

    # Act
    detected = module.is_force_push(command)

    # Assert
    assert detected is True


@pytest.mark.parametrize(
    "command",
    ["git -C /tmp/x push origin feat", "git -C /tmp/x status"],
)
def test_plain_calls_behind_global_options_are_not_force_pushes(command):
    # Arrange
    module = _load_module()

    # Act
    detected = module.is_force_push(command)

    # Assert
    assert detected is False
