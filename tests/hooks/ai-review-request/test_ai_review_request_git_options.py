from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / "ai-review-request.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("_arr_git_options", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_arr_git_options"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("command", "directory"),
    [
        ("git --config-env core.x=ENV push", "/work"),
        ("git --namespace ns push", "/work"),
        ("git --attr-source HEAD push", "/work"),
        ("git -c a=b -C repo push", "/work/repo"),
    ],
)
def test_push_behind_value_options_is_a_trigger(command, directory):
    # Arrange
    module = _load_module()

    # Act
    triggers = module.find_triggers(command, "/work")

    # Assert
    assert [(t.kind.value, t.cwd) for t in triggers] == [("push", directory)]


@pytest.mark.parametrize(
    "command",
    ["git --git-dir /x/.git push", "git --work-tree /x push"],
)
def test_push_against_an_unnamed_repository_is_not_a_trigger(command):
    # Arrange
    module = _load_module()

    # Act
    triggers = module.find_triggers(command, "/work")

    # Assert
    assert triggers == []
