from __future__ import annotations
import os
from pathlib import Path
import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
import subprocess
import sys
from _tdd_gate_helpers import HOOK


@pytest.mark.parametrize(
    "rel_path",
    [
        "src/services/user.py",
        "src/components/Button.tsx",
        "src/utils/format.js",
        "internal/api/handler.go",
        "lib/calculator.rb",
        "app/models/Order.kt",
    ],
)
def test_blocks_new_production_source_without_test(
    tool_use, run_hook, tmp_path, rel_path
):
    # Arrange
    target = tmp_path / rel_path
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 1\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "without a companion test")


def test_blocks_typescript_service(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "src/api/orders.service.ts"
    payload = tool_use("Write", {"file_path": str(target), "content": "export {}"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "BLOCKED")


def test_allows_edit_of_existing_file(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "src" / "user.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n")
    payload = tool_use(
        "Edit",
        {
            "file_path": str(target),
            "old_string": "x = 1",
            "new_string": "x = 2",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_write_overwriting_existing_file(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "src" / "user.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n")
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 2\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize("tool_name", ["Bash", "Read", "Grep", "Glob", "WebFetch"])
def test_allows_unrelated_tools(tool_use, run_hook, tool_name):
    # Arrange
    payload = tool_use(tool_name, {"command": "echo hi"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_bypass_env_var_disables_check(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "src/user.py"
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 1"})

    # Act
    result = run_hook(HOOK, payload, env={"TDD_GATE_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_handles_missing_tool_input(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write")

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_handles_empty_file_path(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": "", "content": "x"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_malformed_json():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "tdd-gate.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not json at all",
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={
            **os.environ,
            "CLAUDE_HOOK_AUDIT_DISABLE": "1",
            "CLAUDE_BYPASS_STATE": os.devnull,
        },
    )

    # Assert
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr
