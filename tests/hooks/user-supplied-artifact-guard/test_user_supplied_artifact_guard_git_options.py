from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_blocked

HOOK = "user-supplied-artifact-guard"
HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("_usag_git_options", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "command",
    [
        'git -C "/tmp/my repo" add game.gba',
        "git -C '/tmp/my repo' add game.gba",
        "git -c core.x=y --no-pager add game.gba",
    ],
)
def test_add_behind_global_options_yields_its_paths(command):
    # Arrange
    module = _load_module()

    # Act
    paths = module._explicit_add_paths(command)

    # Assert
    assert paths == ["game.gba"]


def test_add_behind_a_spaced_dash_c_path_is_blocked(tmp_path, tool_use, run_hook):
    # Arrange
    repo = tmp_path / "my repo"
    repo.mkdir()
    artifact = tmp_path / "game.gba"
    artifact.write_bytes(b"rom")
    payload = tool_use("Bash", {"command": f'git -C "{repo}" add {artifact}'})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, ".gba is a user-supplied artifact extension")
