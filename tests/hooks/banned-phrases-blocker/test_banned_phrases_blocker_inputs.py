from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

ROOT = Path(__file__).resolve().parents[3]
HOOK = "banned-phrases-blocker"
HOOK_PATH = ROOT / "hooks" / f"{HOOK}.py"
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "tests"))

from _helpers.cov_env import apply_coverage_env  # noqa: E402
from _lib.bypass_writer import set_bypass  # noqa: E402

PHRASE = "Hope " + "this helps"
DOC = "/tmp/notes/guide.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("_bpb_inputs", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_an_empty_path_is_not_a_skipped_doc():
    # Arrange
    module = _load_module()

    # Act
    skipped = module.is_skipped_md_path("")

    # Assert
    assert skipped is False


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Write", {"file_path": DOC, "content": 7}),
        ("Edit", {"file_path": DOC, "new_string": None}),
        ("MultiEdit", {"file_path": DOC, "edits": ["text", {"new_string": 3}]}),
        ("MultiEdit", {"file_path": DOC, "edits": None}),
    ],
)
def test_text_fields_that_are_not_strings_are_ignored(
    tool, tool_input, tool_use, run_hook
):
    # Arrange
    payload = tool_use(tool, tool_input)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_banned_phrase_in_one_multiedit_entry_blocks(tool_use, run_hook):
    # Arrange
    edits = ["text", {"new_string": 3}, {"new_string": PHRASE}]
    payload = tool_use("MultiEdit", {"file_path": DOC, "edits": edits})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, f"{DOC} [2]")


def test_a_hook_disabled_by_profile_allows(tool_use, run_hook):
    # Arrange
    payload = tool_use("Edit", {"file_path": DOC, "new_string": PHRASE})

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_DISABLED_HOOKS": HOOK})

    # Assert
    assert_allowed(result)


def test_a_live_bypass_entry_allows(tmp_path, tool_use, run_hook):
    # Arrange
    state = tmp_path / "bypass.json"
    set_bypass(HOOK, ttl_seconds=120, state_path=state)
    payload = tool_use("Edit", {"file_path": DOC, "new_string": PHRASE})

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
