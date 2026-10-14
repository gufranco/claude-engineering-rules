from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _helpers.cov_env import apply_coverage_env  # noqa: E402
from _scope_guard_helpers import HOOK, make_plan


def test_blocks_when_target_outside_scope(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py", "tests/hooks/foo/test_foo.py"])
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/unrelated.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "add its path to the plan")


def test_blocks_when_editing_unrelated_test(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py"])
    payload = tool_use(
        "Edit",
        {
            "file_path": str(tmp_path / "tests/hooks/bar/test_bar.py"),
            "old_string": "x",
            "new_string": "y",
        },
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "BLOCKED: editing `test_bar.py` which is not listed in the active plan `",
    )


@pytest.mark.parametrize("tool_name", ["Bash", "Read", "Grep", "Glob"])
def test_allows_unrelated_tools(tool_use, run_hook, tool_name, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py"])
    payload = tool_use(tool_name, {"command": "ls"}, cwd=str(tmp_path))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_bypass_env_var_disables_check(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py"])
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/other.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload, env={"SCOPE_GUARD_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_handles_missing_file_path(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py"])
    payload = tool_use("Write", {}, cwd=str(tmp_path))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_malformed_payload_blocks():
    # Arrange
    hook = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input="not json",
        capture_output=True,
        text=True,
        env=apply_coverage_env({**os.environ, "CLAUDE_BYPASS_STATE": os.devnull}),
        check=False,
        timeout=30,
    )

    # Assert
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr


def test_the_block_is_reported_as_a_deny_decision(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py"])
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/unrelated.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    decision = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]
    assert (result.code, decision) == (2, "deny")
