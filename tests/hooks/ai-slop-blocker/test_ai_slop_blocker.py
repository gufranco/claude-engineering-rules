from __future__ import annotations


import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "ai-slop-blocker"
DOC = "/repo/docs/notes.md"

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))
from _lib.output import validate_block_message  # noqa: E402


@pytest.mark.parametrize(
    ("code", "text"),
    [
        ("SLOP001", "The cache is not just a store, but a contract with the caller."),
        ("SLOP001", "It's not about speed. It's about correctness under retry."),
        ("SLOP001", "The queue is more than just a buffer."),
        ("SLOP002", "This release stands as a testament to the team's work."),
        ("SLOP002", "The scheduler plays a crucial role in the pipeline."),
        ("SLOP002", "This underscores the importance of bounded retries."),
        ("SLOP003", "The lock is released on exit, highlighting the value of RAII."),
        ("SLOP003", "Retries are capped at three, reflecting the team's caution."),
        ("SLOP004", "Experts argue that the approach does not scale."),
        ("SLOP004", "Studies show that the cache hit rate improves."),
        ("SLOP004", "This pattern is widely considered an anti-pattern."),
        (
            "SLOP005",
            "While specific details about the outage are not documented, "
            "it likely stemmed from a lock contention issue.",
        ),
        ("SLOP005", "As of my last update, the endpoint returned a 200."),
        ("SLOP006", "This module serves as the entry point for the worker."),
        ("SLOP006", "The cluster boasts three replicas across two regions."),
        ("SLOP007", "Look, the migration has to run before the deploy."),
        ("SLOP007", "To be fair, the original design predates the constraint."),
        ("SLOP008", "In short, the retry budget is the binding constraint."),
        ("SLOP008", "The key takeaway is that the lock must span both writes."),
        ("SLOP010", "I hope this helps. Let me know if you'd like me to expand it."),
        ("SLOP010", "Here's a template you can customize for your service."),
        ("SLOP011", "Contact [insert team name] before running the migration."),
        ("SLOP011", "Access date recorded as 2025-XX-XX in the citation."),
        ("SLOP012", "The handler’s timeout is 30 seconds."),
        (
            "SLOP015",
            "Two websites were checked and refused the request (HTTP 403), "
            "so they add nothing here.",
        ),
        ("SLOP015", "The datasheet could not be located, so the timing is inferred."),
        ("SLOP015", "We could not find a public schematic for the board."),
        ("SLOP015", "A search for the part number turned up nothing."),
        ("SLOP015", "The pinout was verified on 2026-10-11 against the board."),
        ("SLOP015", "The archive returned no results for the chip."),
    ],
)
def test_detector_blocks_its_tell(tool_use, run_hook, code, text):
    # Arrange
    payload = tool_use("Write", {"file_path": DOC, "content": f"# Notes\n\n{text}\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
    assert code in stderr


def test_a_single_vocabulary_hit_is_allowed(tool_use, run_hook):
    # Arrange
    single = tool_use(
        "Write",
        {"file_path": DOC, "content": "# Notes\n\nThe migration is meticulous.\n"},
    )

    # Act
    result = run_hook(HOOK, single)

    # Assert
    assert_allowed(result)


def test_two_distinct_vocabulary_hits_are_blocked(tool_use, run_hook):
    # Arrange
    doubled = tool_use(
        "Write",
        {
            "file_path": DOC,
            "content": (
                "# Notes\n\nThe meticulous rollout will pave the way "
                "for a myriad of follow-on changes.\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, doubled)

    # Assert
    assert_blocked(result, "SLOP009")


def test_fenced_code_is_masked(tool_use, run_hook):
    # Arrange
    content = (
        "# Notes\n\nThe parser rejects the header.\n\n"
        "```python\n"
        'note = "This stands as a testament to the design"\n'
        "```\n"
    )
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_inline_code_is_masked(tool_use, run_hook):
    # Arrange
    content = "# Notes\n\nThe linter flags `plays a crucial role` in prose.\n"
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_line_number_survives_masking(tool_use, run_hook):
    # Arrange
    content = (
        "# Notes\n\n"
        "```python\n"
        "value = 1\n"
        "```\n\n"
        "The scheduler plays a crucial role here.\n"
    )
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
    assert "line 7" in stderr


def test_clean_prose_is_allowed(tool_use, run_hook):
    # Arrange
    content = (
        "# Retry budget\n\n"
        "The worker retries three times, then routes the message to the "
        "dead-letter queue. The budget is three because the p99 downstream "
        "recovery took 8 seconds across 200 sampled runs.\n"
    )
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_non_markdown_file_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/worker.ts",
            "content": "// This stands as a testament to nothing\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_rule_file_itself_is_skipped(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/x/.claude/rules/anti-slop.md",
            "content": "It's not X, it's Y. This stands as a testament.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_publishing_bash_is_scanned(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                "gh pr comment 12 --body 'This stands as a testament to the fix.'"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
    assert "SLOP002" in stderr


def test_non_publishing_bash_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash", {"command": "echo 'this stands as a testament to nothing'"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_edit_scans_new_string_only(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": DOC,
            "old_string": "The worker retries.",
            "new_string": "The worker retries, underscoring the design.",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
    assert "SLOP003" in stderr


def test_multiedit_reports_the_offending_index(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": DOC,
            "edits": [
                {"old_string": "a", "new_string": "The queue drains in order."},
                {"old_string": "b", "new_string": "Experts argue this is wrong."},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
    assert "SLOP004" in stderr
    assert "[1]" in stderr


def test_env_bypass_allows(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": DOC, "content": "This stands as a testament to the design.\n"},
    )

    # Act
    result = run_hook(HOOK, payload, env={"AI_SLOP_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_agent_prompts_are_out_of_scope(tool_use, run_hook):
    # Arrange
    payload = tool_use("Agent", {"prompt": "This stands as a testament to the design."})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_block_message_matches_canonical_schema(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": DOC, "content": "This stands as a testament to the design.\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
    assert validate_block_message(stderr) == []
