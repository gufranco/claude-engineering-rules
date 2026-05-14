"""Agent/Task meta-question coverage for banned-phrases-blocker.

Validates the Agent/Task branch added per
`specs/2026-05-13-smart-questions-improvements/plan.md`. The hook must
block subagent prompts that lead with a meta-question phrase and must
not interfere with Bash, Write, Edit, or MultiEdit payloads.

Source rule: `~/.claude/rules/smart-questions.md` Ship the Question.
"""

from __future__ import annotations

import pytest

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
def test_agent_tool_blocks_leading_meta_phrase(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use("Agent", {"prompt": phrase})

    # Act / Assert
    assert_blocks(HOOK, payload, "subagent prompt starts with a meta-question")


@pytest.mark.parametrize("phrase", LEADING_META_PHRASES)
def test_task_tool_blocks_leading_meta_phrase(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use("Task", {"prompt": phrase})

    # Act / Assert
    assert_blocks(HOOK, payload, "subagent prompt starts with a meta-question")


def test_meta_phrase_mid_prompt_is_allowed(tool_use, assert_allows):
    # Arrange
    prompt = (
        "Find callers of createUser at services/userService.ts:42. "
        "Report file:line for each caller. Under 200 words. "
        "Some users ask Can you find this? but we already know."
    )
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_meta_phrase_with_leading_whitespace_is_blocked(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Agent", {"prompt": "   \n  Can you check this please"})

    # Act / Assert
    assert_blocks(HOOK, payload, "meta-question")


def test_case_insensitive_match(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Agent", {"prompt": "CAN YOU FIND the test fixture"})

    # Act / Assert
    assert_blocks(HOOK, payload, "meta-question")


def test_empty_prompt_does_not_block(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Agent", {"prompt": ""})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_whitespace_only_prompt_does_not_block(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Agent", {"prompt": "   \n\t  "})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_missing_prompt_field_does_not_block(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Agent", {})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_non_string_prompt_does_not_block(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Agent", {"prompt": 12345})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_well_formed_agent_prompt_passes(tool_use, assert_allows):
    # Arrange
    prompt = (
        "Find callers of createUser at services/userService.ts:42. "
        "Report file:line for each caller. Under 200 words."
    )
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_disable_env_bypasses_agent_meta_block(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Agent", {"prompt": "Can you find the bug"})

    # Act / Assert
    assert_allows(HOOK, payload, env={"BANNED_PHRASES_DISABLE": "1"})


def test_bash_with_meta_phrase_in_command_does_not_match_agent_branch(
    tool_use, assert_allows
):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "echo 'Can you find this' > /tmp/notes.txt"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_write_with_meta_phrase_in_code_file_does_not_match_agent_branch(
    tool_use, assert_allows
):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// Can you find this todo later\nconst x = 1;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_agent_prompt_with_meta_phrase_takes_priority_over_other_check(
    tool_use, assert_blocks
):
    # Arrange
    prompt = "Can you find the bug. Hope this helps you understand."
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    _, stderr = assert_blocks(HOOK, payload, "meta-question")
    assert "Leading phrase" in stderr
