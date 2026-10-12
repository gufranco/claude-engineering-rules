from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = ROOT / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from _lib.git_invocation import FORCE_PUSH_LONG, FORCE_PUSH_SHORT  # noqa: E402

FORCE = "--" + "force"
SHORT = "-" + "f"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"_{name.replace('-', '_')}_flags", HOOKS_DIR / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "command",
    [
        f"git push {SHORT}u origin feat",
        f"git push -u{SHORT[1:]} origin feat",
        f"git push origin feat {SHORT}",
        f"git -C /tmp/x push {SHORT} origin feat",
        f"git push {FORCE} origin feat",
        f"git push {FORCE}-with-lease origin feat",
        "git push origin +feat",
    ],
)
def test_every_force_form_is_a_force_push(command):
    # Arrange
    module = _load("force-push-during-review")

    # Act
    detected = module.is_force_push(command)

    # Assert
    assert detected is True


@pytest.mark.parametrize(
    "command",
    [
        f"git push origin feat && rm {SHORT} stale.log",
        f"git push origin feat; docker rm {FORCE} box",
        f"git push {FORCE}-if-includes origin feat",
        "git push -u origin feat",
    ],
)
def test_a_force_flag_outside_the_push_is_not_a_force_push(command):
    # Arrange
    module = _load("force-push-during-review")

    # Act
    detected = module.is_force_push(command)

    # Assert
    assert detected is False


@pytest.mark.parametrize("shared", [FORCE_PUSH_LONG, FORCE_PUSH_SHORT])
def test_the_blocker_uses_the_shared_force_patterns(shared):
    # Arrange
    module = _load("dangerous-command-blocker")

    # Act
    patterns = {pattern for pattern, _reason in module.CRITICAL_PATHS}

    # Assert
    assert shared in patterns
