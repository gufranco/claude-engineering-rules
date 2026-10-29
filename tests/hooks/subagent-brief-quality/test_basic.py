from __future__ import annotations
from _helpers.hook_assertions import assert_allowed, assert_blocked
import json
import os
import subprocess
import sys
from pathlib import Path


HOOK = "subagent-brief-quality"


def test_all_four_heuristics_pass(tool_use, run_hook):
    # Arrange
    prompt = (
        "Find callers of createUser at services/userService.ts:42. "
        "Report file:line for each caller. Under 200 words."
    )
    payload = tool_use("Agent", {"prompt": prompt})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_one_failed_heuristic_reaches_the_model(tool_use, run_hook):
    # Arrange
    prompt = (
        "Find callers of createUser at services/userService.ts:42. "
        "Report file:line for each caller."
    )
    payload = tool_use("Agent", {"prompt": prompt})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert (
        result.code,
        "length cap" in context.lower(),
        "Investigate this advisory" in context,
    ) == (0, True, True)


def test_one_heuristic_fails_is_advisory(tool_use, run_hook):
    # Arrange
    prompt = (
        "Find callers of createUser at services/userService.ts:42. "
        "Report file:line for each caller."
    )
    payload = tool_use("Agent", {"prompt": prompt})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_two_heuristics_fail_blocks(tool_use, run_hook):
    # Arrange
    prompt = "Find callers of createUser at services/userService.ts:42."
    payload = tool_use("Agent", {"prompt": prompt})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, "fails 2 of 4 quality heuristics")
    assert "missing response-length cap" in stderr
    assert "missing output shape" in stderr


def test_three_heuristics_fail_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {"prompt": "Look into the issue."})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "fails 3 of 4 quality heuristics")


def test_all_four_heuristics_fail_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {"prompt": "Can you find the bug"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, "fails 4 of 4 quality heuristics")
    assert "missing specific reference" in stderr
    assert "missing response-length cap" in stderr
    assert "missing output shape" in stderr
    assert "leading meta-prompt" in stderr


def test_task_tool_is_covered(tool_use, run_hook):
    # Arrange
    payload = tool_use("Task", {"prompt": "Can you find the bug"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "fails 4 of 4 quality heuristics")


def test_non_agent_tool_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "echo 'this prompt has none of the required heuristics'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_tool_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/x.ts", "content": "const x = 1;"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_empty_prompt_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {"prompt": ""})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_whitespace_only_prompt_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {"prompt": "   \n\t "})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_missing_prompt_field_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_non_string_prompt_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {"prompt": ["a", "b"]})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: subagent-brief-quality could not read its input: tool_input.prompt is not a",
    )


def test_disable_env_bypasses_block(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {"prompt": "Can you find the bug"})

    # Act
    result = run_hook(HOOK, payload, env={"SUBAGENT_BRIEF_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_disable_env_value_other_than_one_does_not_bypass(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {"prompt": "Look into the issue."})

    # Act
    result = run_hook(HOOK, payload, env={"SUBAGENT_BRIEF_DISABLE": "0"})

    # Assert
    assert_blocked(result, "Blocked: subagent prompt fails 3 of 4 quality heuristics.")


def test_block_message_includes_remediation_hint(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {"prompt": "Look into the issue."})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(
        result, "Blocked: subagent prompt fails 3 of 4 quality heuristics."
    )
    assert "standards/smart-questions.md" in stderr
    assert "Briefing Subagents" in stderr
    assert "Fix:" in stderr
    assert "SUBAGENT_BRIEF_DISABLE=1" in stderr


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "subagent-brief-quality.py"
    )
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    env["CLAUDE_BYPASS_STATE"] = os.devnull

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
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr
