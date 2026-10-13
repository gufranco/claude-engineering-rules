from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "banned-phrases-blocker"

LEADING_META_PHRASES = [
    "Can you find the bug",
    "Can you check this file",
    "Can you look at services/userService.ts",
    "Could you find references to createUser",
    "Could you check the regex",
    "Could you look up the API contract",
    "Help me with the migration",
    "Help me find the failing test",
    "Quick question about routing",
    "Anyone good at TypeScript types",
    "Anyone know the latest Prisma syntax",
    "Any expert on Postgres locking",
    "Should I ask the team about this",
    "Can I ask a quick question",
    "Just wondering if this works",
]


@pytest.mark.parametrize("phrase", LEADING_META_PHRASES)
def test_agent_tool_blocks_leading_meta_phrase(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use("Agent", {"prompt": phrase})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "subagent prompt starts with a meta-question")


@pytest.mark.parametrize("phrase", LEADING_META_PHRASES)
def test_task_tool_blocks_leading_meta_phrase(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use("Task", {"prompt": phrase})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "subagent prompt starts with a meta-question")


def test_meta_phrase_mid_prompt_is_allowed(tool_use, run_hook):
    # Arrange
    prompt = (
        "Find callers of createUser at services/userService.ts:42. "
        "Report file:line for each caller. Under 200 words. "
        "Some users ask Can you find this? but we already know."
    )
    payload = tool_use("Agent", {"prompt": prompt})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_meta_phrase_with_leading_whitespace_is_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {"prompt": "   \n  Can you check this please"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "meta-question")


def test_case_insensitive_match(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {"prompt": "CAN YOU FIND the test fixture"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "meta-question")


def test_empty_prompt_does_not_block(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {"prompt": ""})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_whitespace_only_prompt_does_not_block(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {"prompt": "   \n\t  "})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_missing_prompt_field_does_not_block(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_non_string_prompt_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {"prompt": 12345})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: banned-phrases-blocker could not read its input: tool_input.prompt is not a",
    )


def test_well_formed_agent_prompt_passes(tool_use, run_hook):
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


def test_disable_env_bypasses_agent_meta_block(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {"prompt": "Can you find the bug"})

    # Act
    result = run_hook(HOOK, payload, env={"BANNED_PHRASES_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_bash_with_meta_phrase_in_command_does_not_match_agent_branch(
    tool_use, run_hook
):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "echo 'Can you find this' > /tmp/notes.txt"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_with_meta_phrase_in_code_file_does_not_match_agent_branch(
    tool_use, run_hook
):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// Can you find this todo later\nconst x = 1;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_agent_prompt_with_meta_phrase_takes_priority_over_other_check(
    tool_use, run_hook
):
    # Arrange
    prompt = "Can you find the bug. Hope this helps you understand."
    payload = tool_use("Agent", {"prompt": prompt})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, "meta-question")
    assert "Leading phrase" in stderr
