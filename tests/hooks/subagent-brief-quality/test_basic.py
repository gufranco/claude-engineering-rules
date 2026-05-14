"""Severity ladder and bypass coverage for subagent-brief-quality.

Validates the three-tier severity behavior:
  - 0 failures: silent pass
  - 1 failure: advisory audit, exit 0
  - 2+ failures: block (exit 2)

Source rule: `~/.claude/rules/smart-questions.md` Briefing Subagents.
"""

from __future__ import annotations


HOOK = "subagent-brief-quality"


def test_all_four_heuristics_pass(tool_use, assert_allows):
    # Arrange
    prompt = (
        "Find callers of createUser at services/userService.ts:42. "
        "Report file:line for each caller. Under 200 words."
    )
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_one_heuristic_fails_is_advisory(tool_use, assert_allows):
    # Arrange
    prompt = (
        "Find callers of createUser at services/userService.ts:42. "
        "Report file:line for each caller."
    )
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_two_heuristics_fail_blocks(tool_use, assert_blocks):
    # Arrange
    prompt = "Find callers of createUser at services/userService.ts:42."
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    _, stderr = assert_blocks(HOOK, payload, "fails 2 of 4 quality heuristics")
    assert "missing response-length cap" in stderr
    assert "missing output shape" in stderr


def test_three_heuristics_fail_blocks(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Agent", {"prompt": "Look into the issue."})

    # Act / Assert
    _, stderr = assert_blocks(HOOK, payload, "fails 3 of 4 quality heuristics")


def test_all_four_heuristics_fail_blocks(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Agent", {"prompt": "Can you find the bug"})

    # Act / Assert
    _, stderr = assert_blocks(HOOK, payload, "fails 4 of 4 quality heuristics")
    assert "missing specific reference" in stderr
    assert "missing response-length cap" in stderr
    assert "missing output shape" in stderr
    assert "leading meta-prompt" in stderr


def test_task_tool_is_covered(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Task", {"prompt": "Can you find the bug"})

    # Act / Assert
    assert_blocks(HOOK, payload, "fails 4 of 4 quality heuristics")


def test_non_agent_tool_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "echo 'this prompt has none of the required heuristics'"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_write_tool_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/x.ts", "content": "const x = 1;"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_empty_prompt_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Agent", {"prompt": ""})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_whitespace_only_prompt_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Agent", {"prompt": "   \n\t "})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_missing_prompt_field_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Agent", {})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_non_string_prompt_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Agent", {"prompt": ["a", "b"]})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_disable_env_bypasses_block(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Agent", {"prompt": "Can you find the bug"})

    # Act / Assert
    assert_allows(HOOK, payload, env={"SUBAGENT_BRIEF_DISABLE": "1"})


def test_disable_env_value_other_than_one_does_not_bypass(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Agent", {"prompt": "Look into the issue."})

    # Act / Assert
    assert_blocks(HOOK, payload, env={"SUBAGENT_BRIEF_DISABLE": "0"})


def test_block_message_includes_remediation_hint(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Agent", {"prompt": "Look into the issue."})

    # Act / Assert
    _, stderr = assert_blocks(HOOK, payload)
    assert "rules/smart-questions.md" in stderr
    assert "Briefing Subagents" in stderr
    assert "Fix:" in stderr
    assert "SUBAGENT_BRIEF_DISABLE=1" in stderr


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    import os
    import subprocess
    import sys
    from pathlib import Path

    hook_path = Path("/Users/gufranco/.claude/hooks/subagent-brief-quality.py")
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not valid json",
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )

    # Assert
    assert proc.returncode == 0
