from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from _helpers.hook_assertions import assert_allowed, assert_blocked


HOOK = "ai-process-leak-blocker"


def test_allows_clean_commit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "fix race condition in createUser"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_non_publishing_bash(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "echo Phase 1 of the plan"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_write_to_planning_artifact(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/specs/2026-01-01-foo/plan.md",
            "content": "# Phase 1: scaffolding\n\nMaps to canvas region 2.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_write_to_adr(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/docs/adr/0012-foo.md",
            "content": "# ADR-0012\n\nSupersedes ADR-0008.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_write_to_runbook(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/docs/runbook/incidents.md",
            "content": "# Incident phases\n\nPhase 1: detect.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_write_to_claude_config(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/x/.claude/rules/my-rule.md",
            "content": "# Rule\n\nPhase 1 of the plan is fine here.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_bypass_env_var_allows(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "Phase 1 of the plan"'},
    )

    # Act
    result = run_hook(HOOK, payload, env={"AI_PROCESS_LEAK_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_allows_clean_pr_body(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh pr create --title "feat" --body "Adds a new endpoint for X"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_invalid_json_blocks():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "ai-process-leak-blocker.py"
    )

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env={
            **os.environ,
            "CLAUDE_HOOK_AUDIT_DISABLE": "1",
            "CLAUDE_BYPASS_STATE": os.devnull,
        },
    )

    # Assert
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr


def test_allows_unknown_tool(tool_use, run_hook):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/src/app.ts"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_empty_bash(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_state_of_the_art_in_docs(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/.claude/notes.md",
            "content": "Researching state-of-the-art parsers.",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_with_empty_path_still_checked(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "",
            "content": "Phase 1 of the plan",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_write_with_no_path_still_checked(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"content": "Phase 7 work"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_multiedit_with_non_dict_edit_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/app.ts",
            "edits": ["not-a-dict", {"old_string": "a", "new_string": "clean"}],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: ai-process-leak-blocker could not read its input: tool_input.edits is not a",
    )
