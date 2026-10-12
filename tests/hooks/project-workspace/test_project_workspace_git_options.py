from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = ROOT / "hooks" / "project-workspace.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.git_invocation import OPTIONS_WITH_SEPARATE_VALUE  # noqa: E402


def _load_module():
    spec = importlib.util.spec_from_file_location("_pw_git_options", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_pw_git_options"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("tokens", "base"),
    [
        (["git", "--config-env", "core.x=ENV", "add", "-f", "docs"], "/w"),
        (["git", "--attr-source", "HEAD", "add", "-f", "docs"], "/w"),
        (["git", "-c", "a=b", "-C", "sub", "add", "-f", "docs"], "/w/sub"),
        (["git", "--namespace", "ns", "add", "-f", "docs"], "/w"),
    ],
)
def test_value_options_are_skipped_before_the_subcommand(tokens, base):
    # Arrange
    module = _load_module()

    # Act
    call = module._git_call(tokens, Path("/w"))

    # Assert
    assert (call.base, call.subcommand, call.args) == (
        Path(base),
        "add",
        ("-f", "docs"),
    )


def test_the_value_option_set_matches_the_shared_normaliser():
    # Arrange
    expected = frozenset(OPTIONS_WITH_SEPARATE_VALUE)

    # Act
    options = _load_module().GIT_OPTIONS_WITH_VALUE

    # Assert
    assert options == expected
