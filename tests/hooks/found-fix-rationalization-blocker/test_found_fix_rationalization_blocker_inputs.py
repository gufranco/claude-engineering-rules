from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

ROOT = Path(__file__).resolve().parents[3]
HOOK = "found-fix-rationalization-blocker"
HOOK_PATH = ROOT / "hooks" / f"{HOOK}.py"
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "tests"))

from _helpers.cov_env import apply_coverage_env  # noqa: E402
from _lib.bypass_writer import set_bypass  # noqa: E402

DODGE = "orthogonal " + "to this task"
DOC = "/tmp/project/notes.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("_ffrb_inputs", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_an_empty_path_is_not_skipped():
    # Arrange
    module = _load_module()

    # Act
    skipped = module.is_skipped_path("")

    # Assert
    assert skipped is False


@pytest.mark.parametrize(
    ("tool", "tool_input", "field"),
    [
        ("Write", {"file_path": DOC, "content": DODGE}, "in content"),
        ("Edit", {"file_path": DOC, "new_string": DODGE}, "in new_string"),
        (
            "MultiEdit",
            {
                "file_path": DOC,
                "edits": ["x", {"new_string": 1}, {"new_string": DODGE}],
            },
            "in edits[2].new_string",
        ),
    ],
)
def test_a_rationalization_in_any_text_field_blocks(
    tool, tool_input, field, tool_use, run_hook
):
    # Arrange
    payload = tool_use(tool, tool_input)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, field)


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Write", {"file_path": DOC, "content": 3}),
        ("Edit", {"file_path": DOC, "new_string": None}),
        ("MultiEdit", {"file_path": DOC, "edits": None}),
        ("Write", {"file_path": "/x/rules/found-fix.md", "content": DODGE}),
        ("Read", {"file_path": DOC}),
    ],
)
def test_text_it_does_not_read_is_allowed(tool, tool_input, tool_use, run_hook):
    # Arrange
    payload = tool_use(tool, tool_input)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "env",
    [{"FOUND_FIX_RATIONALIZATION_DISABLE": "1"}, {"CLAUDE_DISABLED_HOOKS": HOOK}],
)
def test_an_explicit_switch_allows(env, tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": DOC, "content": DODGE})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_a_live_bypass_entry_allows(tmp_path, tool_use, run_hook):
    # Arrange
    state = tmp_path / "bypass.json"
    set_bypass(HOOK, ttl_seconds=120, state_path=state)
    payload = tool_use("Write", {"file_path": DOC, "content": DODGE})

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(state)})

    # Assert
    assert_allowed(result)


def test_a_payload_that_is_not_json_allows():
    # Arrange
    env = apply_coverage_env(dict(os.environ))
    env["CLAUDE_BYPASS_STATE"] = os.devnull

    # Act
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="not json",
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )

    # Assert
    assert (proc.returncode, proc.stderr) == (0, "")
