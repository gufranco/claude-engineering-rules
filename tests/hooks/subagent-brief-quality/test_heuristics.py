"""Per-heuristic coverage for subagent-brief-quality.

Exercises each of the four heuristics in isolation by crafting prompts
that satisfy exactly three of the four checks and varying which one
fails. Each prompt below has a documented "missing" element; the test
asserts the hook produces an advisory pass (one heuristic failed).

Source rule: `~/.claude/rules/smart-questions.md` Briefing Subagents.
"""

from __future__ import annotations

import pytest

HOOK = "subagent-brief-quality"


SPECIFIC_REFERENCE_SAMPLES = [
    "services/userService.ts",
    "src/components/Button.tsx",
    "lib/api/handler.py",
    "internal/auth/main.go",
    "src/lib.rs",
    "scripts/deploy.sh",
    "config/database.yml",
    "schema.prisma",
    "models/User.kt",
    "src/index.swift",
    "services/userService.ts:42",
    "createUser()",
    "fetchData()",
    "E1234",
    "P404",
    "error code E1001",
]


@pytest.mark.parametrize("ref", SPECIFIC_REFERENCE_SAMPLES)
def test_specific_reference_pattern_matches(tool_use, assert_allows, ref):
    # Arrange
    # Arrange
    prompt = f"Investigate {ref}. Return a short report. Under 100 words."
    # Act
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    # Assert
    assert_allows(HOOK, payload)


LENGTH_CAP_SAMPLES = [
    "Under 200 words",
    "under 50 chars",
    "Under 10 sentences",
    "Under 3 paragraphs",
    "under 5 lines",
    "Under 1000 tokens",
    "no more than 100 words",
    "at most 5 sentences",
    "max 200 words",
    "maximum 50 lines",
    "fewer than 100 words",
    "less than 5 paragraphs",
    "up to 200 words",
    "200 words max",
    "100 words limit",
    "5 sentences cap",
    "50 words or less",
    "one sentence",
    "single paragraph",
    "single line",
    "brief",
    "briefly",
    "be terse",
    "short answer",
    "short report",
    "short response",
    "short summary",
]


@pytest.mark.parametrize("cap", LENGTH_CAP_SAMPLES)
def test_length_cap_pattern_matches(tool_use, assert_allows, cap):
    # Arrange
    # Arrange
    prompt = f"Investigate path/to/file.ts. Return a list. {cap}."
    # Act
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    # Assert
    assert_allows(HOOK, payload)


OUTPUT_SHAPE_KEYWORDS = [
    "report",
    "return",
    "produce",
    "output",
    "list",
    "table",
    "summary",
    "findings",
    "result",
    "answer",
    "punch list",
    "checklist",
    "diff",
    "patch",
    "plan",
]


@pytest.mark.parametrize("kw", OUTPUT_SHAPE_KEYWORDS)
def test_output_shape_keyword_matches(tool_use, assert_allows, kw):
    # Arrange
    # Arrange
    prompt = f"Look at services/x.ts:10. Produce a {kw}. Under 100 words."
    # Act
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    # Assert
    assert_allows(HOOK, payload)


META_LEADING_SAMPLES = [
    "Can you find the bug",
    "Can you check the file",
    "Can you look at this",
    "Can you help me",
    "Could you find the issue",
    "Could you check this",
    "Could you look at this",
    "Could you help me",
    "Help me with this",
    "Help me find the bug",
    "Quick question about routing",
    "Anyone good at TypeScript",
    "Anyone know the answer",
    "Any expert here",
    "Should I ask the team",
    "Can I ask a question",
    "Just wondering about this",
    "Hi!",
    "Hello",
]


@pytest.mark.parametrize("phrase", META_LEADING_SAMPLES)
def test_meta_leading_pattern_blocks(tool_use, assert_blocks, phrase):
    # Arrange
    # Arrange
    # Act
    payload = tool_use("Agent", {"prompt": phrase})

    # Act / Assert
    # Assert
    assert_blocks(HOOK, payload, "leading meta-prompt")


def test_missing_only_specific_reference_is_advisory(tool_use, assert_allows):
    # Arrange
    # Arrange
    prompt = "Find the failing tests. Return a list. Under 200 words."
    # Act
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    # Assert
    assert_allows(HOOK, payload)


def test_missing_only_length_cap_is_advisory(tool_use, assert_allows):
    # Arrange
    # Arrange
    prompt = (
        "Find callers of createUser at services/userService.ts:42. "
        "Return a list of file:line pairs."
    )
    # Act
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    # Assert
    assert_allows(HOOK, payload)


def test_missing_only_output_shape_is_advisory(tool_use, assert_allows):
    # Arrange
    # Arrange
    prompt = "Investigate services/userService.ts:42 thoroughly. Under 200 words."
    # Act
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    # Assert
    assert_allows(HOOK, payload)


def test_missing_specific_reference_and_length_cap_blocks(tool_use, assert_blocks):
    # Arrange
    # Arrange
    prompt = "Find the failing tests. Return a list."
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    # Act
    _, stderr = assert_blocks(HOOK, payload, "fails 2 of 4")
    # Assert
    assert "missing specific reference" in stderr
    assert "missing response-length cap" in stderr


def test_missing_specific_reference_and_output_shape_blocks(tool_use, assert_blocks):
    # Arrange
    # Arrange
    prompt = "Look into the failing tests carefully. Under 200 words."
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    # Act
    _, stderr = assert_blocks(HOOK, payload, "fails 2 of 4")
    # Assert
    assert "missing specific reference" in stderr
    assert "missing output shape" in stderr


def test_missing_length_cap_and_output_shape_blocks(tool_use, assert_blocks):
    # Arrange
    # Arrange
    prompt = "Investigate services/userService.ts:42 thoroughly."
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    # Act
    _, stderr = assert_blocks(HOOK, payload, "fails 2 of 4")
    # Assert
    assert "missing response-length cap" in stderr
    assert "missing output shape" in stderr


def test_meta_leading_alone_blocks_all_four(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Agent", {"prompt": "Hi"})

    # Act / Assert
    _, stderr = assert_blocks(HOOK, payload, "fails 4 of 4")


def test_meta_with_one_other_failure_blocks_with_meta_message(tool_use, assert_blocks):
    # Arrange
    # Arrange
    prompt = (
        "Can you find callers of createUser at services/userService.ts:42. "
        "Return a list of file:line pairs."
    )
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    # Act
    _, stderr = assert_blocks(HOOK, payload, "fails 2 of 4")
    # Assert
    assert "leading meta-prompt" in stderr
    assert "missing response-length cap" in stderr


def test_meta_with_complete_brief_is_advisory(tool_use, assert_allows):
    # Arrange
    # Arrange
    prompt = (
        "Can you find callers of createUser at services/userService.ts:42. "
        "Return a list of file:line pairs. Under 200 words."
    )
    # Act
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    # Assert
    assert_allows(HOOK, payload)


def test_function_with_parens_counts_as_specific_reference(tool_use, assert_allows):
    # Arrange
    # Arrange
    prompt = "Look at createUser() in the auth module. Return a list. Briefly."
    # Act
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    # Assert
    assert_allows(HOOK, payload)


def test_directory_slash_path_counts_as_specific_reference(tool_use, assert_allows):
    # Arrange
    # Arrange
    prompt = "Audit services/auth/handlers. Return a summary. Under 50 words."
    # Act
    payload = tool_use("Agent", {"prompt": prompt})

    # Act / Assert
    # Assert
    assert_allows(HOOK, payload)
