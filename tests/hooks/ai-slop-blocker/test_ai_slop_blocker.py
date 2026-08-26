"""Coverage for ai-slop-blocker's structural slop detectors.

Every detector must fire on its own tell, stay silent on masked code, and
stay silent on the disciplined prose already in this repository.

Source rule: `~/.claude/rules/anti-slop.md`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOK = "ai-slop-blocker"
DOC = "/repo/docs/notes.md"

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))


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
    ],
)
def test_detector_blocks_its_tell(tool_use, assert_blocks, code, text):
    payload = tool_use("Write", {"file_path": DOC, "content": f"# Notes\n\n{text}\n"})

    _exit, stderr = assert_blocks(HOOK, payload)

    assert code in stderr


def test_vocabulary_cluster_needs_two_distinct_hits(
    tool_use, assert_allows, assert_blocks
):
    single = tool_use(
        "Write",
        {"file_path": DOC, "content": "# Notes\n\nThe migration is meticulous.\n"},
    )
    assert_allows(HOOK, single)

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
    _exit, stderr = assert_blocks(HOOK, doubled)
    assert "SLOP009" in stderr


def test_fenced_code_is_masked(tool_use, assert_allows):
    content = (
        "# Notes\n\nThe parser rejects the header.\n\n"
        "```python\n"
        'note = "This stands as a testament to the design"\n'
        "```\n"
    )
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    assert_allows(HOOK, payload)


def test_inline_code_is_masked(tool_use, assert_allows):
    content = "# Notes\n\nThe linter flags `plays a crucial role` in prose.\n"
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    assert_allows(HOOK, payload)


def test_line_number_survives_masking(tool_use, assert_blocks):
    content = (
        "# Notes\n\n"
        "```python\n"
        "value = 1\n"
        "```\n\n"
        "The scheduler plays a crucial role here.\n"
    )
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    _exit, stderr = assert_blocks(HOOK, payload)

    assert "line 7" in stderr


def test_clean_prose_is_allowed(tool_use, assert_allows):
    content = (
        "# Retry budget\n\n"
        "The worker retries three times, then routes the message to the "
        "dead-letter queue. The budget is three because the p99 downstream "
        "recovery took 8 seconds across 200 sampled runs.\n"
    )
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    assert_allows(HOOK, payload)


def test_non_markdown_file_is_ignored(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/worker.ts",
            "content": "// This stands as a testament to nothing\n",
        },
    )

    assert_allows(HOOK, payload)


def test_rule_file_itself_is_skipped(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/x/.claude/rules/anti-slop.md",
            "content": "It's not X, it's Y. This stands as a testament.\n",
        },
    )

    assert_allows(HOOK, payload)


def test_publishing_bash_is_scanned(tool_use, assert_blocks):
    payload = tool_use(
        "Bash",
        {
            "command": (
                "gh pr comment 12 --body 'This stands as a testament to the fix.'"
            )
        },
    )

    _exit, stderr = assert_blocks(HOOK, payload)

    assert "SLOP002" in stderr


def test_non_publishing_bash_is_ignored(tool_use, assert_allows):
    payload = tool_use(
        "Bash", {"command": "echo 'this stands as a testament to nothing'"}
    )

    assert_allows(HOOK, payload)


def test_edit_scans_new_string_only(tool_use, assert_blocks):
    payload = tool_use(
        "Edit",
        {
            "file_path": DOC,
            "old_string": "The worker retries.",
            "new_string": "The worker retries, underscoring the design.",
        },
    )

    _exit, stderr = assert_blocks(HOOK, payload)

    assert "SLOP003" in stderr


def test_multiedit_reports_the_offending_index(tool_use, assert_blocks):
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

    _exit, stderr = assert_blocks(HOOK, payload)

    assert "SLOP004" in stderr
    assert "[1]" in stderr


def test_env_bypass_allows(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": DOC, "content": "This stands as a testament to the design.\n"},
    )

    assert_allows(HOOK, payload, env={"AI_SLOP_DISABLE": "1"})


def test_agent_prompts_are_out_of_scope(tool_use, assert_allows):
    payload = tool_use("Agent", {"prompt": "This stands as a testament to the design."})

    assert_allows(HOOK, payload)


def test_block_message_matches_canonical_schema(tool_use, assert_blocks):
    from _lib.output import validate_block_message

    payload = tool_use(
        "Write",
        {"file_path": DOC, "content": "This stands as a testament to the design.\n"},
    )

    _exit, stderr = assert_blocks(HOOK, payload)

    assert validate_block_message(stderr) == []


def test_repository_corpus_stays_clean(tool_use, assert_allows):
    """The detectors must not fire on the existing disciplined corpus."""
    corpus = sorted((REPO_ROOT / "rules").glob("*.md"))
    assert corpus, "expected rules/*.md to exist"
    for path in corpus:
        if path.name == "anti-slop.md":
            continue
        payload = tool_use(
            "Write",
            {"file_path": str(path), "content": path.read_text(encoding="utf-8")},
        )
        assert_allows(HOOK, payload)


def test_missing_file_path_is_ignored(tool_use, assert_allows):
    payload = tool_use("Write", {"content": "This stands as a testament.\n"})

    assert_allows(HOOK, payload)


def test_unwatched_tool_is_ignored(tool_use, assert_allows):
    payload = tool_use("Read", {"file_path": DOC})

    assert_allows(HOOK, payload)


def test_vocabulary_cluster_ignores_a_repeated_single_word(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": DOC,
            "content": (
                "# Notes\n\nThe meticulous rollout was planned.\n"
                "The meticulous rehearsal followed.\n"
            ),
        },
    )

    assert_allows(HOOK, payload)


def test_repeated_code_reports_its_fix_once(tool_use, assert_blocks):
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": DOC,
            "edits": [
                {"old_string": "a", "new_string": "Experts argue the design is wrong."},
                {"old_string": "b", "new_string": "Studies show the cache is cold."},
            ],
        },
    )

    _exit, stderr = assert_blocks(HOOK, payload)

    assert stderr.count("SLOP004: Name the source") == 1


def test_profile_disable_short_circuits(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": DOC, "content": "This stands as a testament to the design.\n"},
    )

    assert_allows(HOOK, payload, env={"CLAUDE_DISABLED_HOOKS": HOOK})


def test_registry_bypass_short_circuits(tool_use, assert_allows, tmp_path):
    payload = tool_use(
        "Write",
        {"file_path": DOC, "content": "This stands as a testament to the design.\n"},
    )
    registry = tmp_path / "bypass.json"
    registry.write_text(
        json.dumps(
            {
                "version": 1,
                "bypasses": [
                    {
                        "hook": HOOK,
                        "expires_at": "2999-01-01T00:00:00+00:00",
                        "reason": "test",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert_allows(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(registry)})


def test_malformed_stdin_is_ignored():
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "hooks" / "ai-slop-blocker.py")],
        input="not json at all",
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0


def test_nested_list_prose_is_still_scanned(tool_use, assert_blocks):
    content = (
        "# Notes\n\n"
        "- Top level item\n"
        "    - The scheduler plays a crucial role in the pipeline.\n"
    )
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    _exit, stderr = assert_blocks(HOOK, payload)

    assert "SLOP002" in stderr


def test_indented_code_block_is_still_masked(tool_use, assert_allows):
    content = (
        "# Notes\n\nThe snippet below is illustrative.\n\n"
        '    note = "This stands as a testament to the design"\n'
    )
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    assert_allows(HOOK, payload)


def test_code_span_in_a_published_body_is_masked(tool_use, assert_allows):
    payload = tool_use(
        "Bash",
        {
            "command": (
                "gh pr comment 12 --body 'Renamed the helper. "
                "Prefer `is` over `serves as a` in the docstring.'"
            )
        },
    )

    assert_allows(HOOK, payload)


def test_prose_in_a_published_body_is_still_scanned(tool_use, assert_blocks):
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 12 --body 'The helper serves as the entry point.'"},
    )

    _exit, stderr = assert_blocks(HOOK, payload)

    assert "SLOP006" in stderr


def test_named_source_is_not_evasive_attribution(tool_use, assert_allows):
    content = (
        "# Notes\n\nMicrosoft research shows praise replies add work without value.\n"
    )
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    assert_allows(HOOK, payload)


def test_unnamed_source_is_still_evasive_attribution(tool_use, assert_blocks):
    content = "# Notes\n\nResearch shows praise replies add work without value.\n"
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    _exit, stderr = assert_blocks(HOOK, payload)

    assert "SLOP004" in stderr
