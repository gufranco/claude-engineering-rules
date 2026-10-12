from __future__ import annotations

import json
import subprocess
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
    ],
)
def test_detector_blocks_its_tell(tool_use, run_hook, code, text):
    # Arrange
    payload = tool_use("Write", {"file_path": DOC, "content": f"# Notes\n\n{text}\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(result)
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
    _exit, stderr = assert_blocked(result)
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
    _exit, stderr = assert_blocked(result)
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
    _exit, stderr = assert_blocked(result)
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
    _exit, stderr = assert_blocked(result)
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
    _exit, stderr = assert_blocked(result)
    assert validate_block_message(stderr) == []


def test_repository_corpus_is_not_empty():
    # Arrange
    rules_dir = REPO_ROOT / "rules"

    # Act
    corpus = sorted(rules_dir.glob("*.md"))

    # Assert
    assert len(corpus) > 1


@pytest.mark.parametrize(
    "path",
    [
        path
        for path in sorted((REPO_ROOT / "rules").glob("*.md"))
        if path.name != "anti-slop.md"
    ],
    ids=lambda path: path.name,
)
def test_repository_corpus_stays_clean(tool_use, run_hook, path):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": str(path), "content": path.read_text(encoding="utf-8")},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_missing_file_path_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"content": "This stands as a testament.\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_unwatched_tool_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Read", {"file_path": DOC})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_vocabulary_cluster_ignores_a_repeated_single_word(tool_use, run_hook):
    # Arrange
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_repeated_code_reports_its_fix_once(tool_use, run_hook):
    # Arrange
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(result)
    assert stderr.count("SLOP004: Name the source") == 1


def test_profile_disable_short_circuits(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": DOC, "content": "This stands as a testament to the design.\n"},
    )

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_DISABLED_HOOKS": HOOK})

    # Assert
    assert_allowed(result)


def test_registry_bypass_short_circuits(tool_use, run_hook, tmp_path):
    # Arrange
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

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(registry)})

    # Assert
    assert_allowed(result)


def test_malformed_stdin_is_ignored():
    # Arrange
    hook_path = REPO_ROOT / "hooks" / "ai-slop-blocker.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not json at all",
        capture_output=True,
        text=True,
    )

    # Assert
    assert proc.returncode == 0


def test_nested_list_prose_is_still_scanned(tool_use, run_hook):
    # Arrange
    content = (
        "# Notes\n\n"
        "- Top level item\n"
        "    - The scheduler plays a crucial role in the pipeline.\n"
    )
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(result)
    assert "SLOP002" in stderr


def test_indented_code_block_is_still_masked(tool_use, run_hook):
    # Arrange
    content = (
        "# Notes\n\nThe snippet below is illustrative.\n\n"
        '    note = "This stands as a testament to the design"\n'
    )
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_code_span_in_a_published_body_is_masked(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                "gh pr comment 12 --body 'Renamed the helper. "
                "Prefer `is` over `serves as a` in the docstring.'"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_prose_in_a_published_body_is_still_scanned(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 12 --body 'The helper serves as the entry point.'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(result)
    assert "SLOP006" in stderr


def test_named_source_is_not_evasive_attribution(tool_use, run_hook):
    # Arrange
    content = (
        "# Notes\n\nMicrosoft research shows praise replies add work without value.\n"
    )
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_unnamed_source_is_still_evasive_attribution(tool_use, run_hook):
    # Arrange
    content = "# Notes\n\nResearch shows praise replies add work without value.\n"
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(result)
    assert "SLOP004" in stderr


REPLY_ENDPOINT = "repos/acme/widgets/pulls/12/comments/9981/replies"


def test_bold_label_bullet_blocked_in_a_reply(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "reply.json"
    body.write_text(
        '{"body": "- **Fix:** the guard now runs on both paths.\\n'
        '- **Test:** added at tests/orders.spec.ts:142.\\n"}',
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPLY_ENDPOINT} -X POST --input {body}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(result)
    assert "SLOP013" in stderr


def test_heading_blocked_in_a_reply(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "reply.json"
    body.write_text(
        '{"body": "## Summary\\nThe guard now runs on both paths.\\n"}',
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPLY_ENDPOINT} -X POST --input {body}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(result)
    assert "SLOP014" in stderr


def test_plain_reply_is_allowed(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "reply.json"
    body.write_text(
        '{"body": "Fixed in a1b2c3d. The round-robin path skipped the guard, '
        'so both routes go through one helper now."}',
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPLY_ENDPOINT} -X POST --input {body}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_bold_label_bullet_allowed_in_repo_markdown(tool_use, run_hook):
    # Arrange
    content = (
        "# Notes\n\n"
        "- **Idempotency key:** required on every write.\n"
        "- **Storage:** durable, with a TTL matching the retry window.\n"
    )
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_heading_allowed_in_a_pr_description(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "description.md"
    body.write_text(
        "## What\n\nThe guard now runs on both placement paths.\n\n"
        "- **Testing:** the full suite, plus a new case at tests/orders.spec.ts:142.\n",
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": f"gh pr create --title fix --body-file {body}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_inline_reply_body_is_scanned(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                f"gh api {REPLY_ENDPOINT} -X POST "
                "-f body='## Summary\nFixed on both paths.'"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(result)
    assert "SLOP014" in stderr


def test_review_payload_inline_comment_bodies_are_scanned(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "review.json"
    body.write_text(
        '{"event": "COMMENT", "body": "", "comments": '
        '[{"path": "a.ts", "line": 4, "body": "- **Issue:** off by one."}]}',
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {
            "command": (
                f"gh api repos/acme/widgets/pulls/12/reviews -X POST --input {body}"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(result)
    assert "SLOP013" in stderr


def test_unreadable_payload_path_falls_back_to_the_literal(
    tool_use, run_hook, tmp_path
):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPLY_ENDPOINT} -X POST --input {tmp_path}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_unparseable_reply_command_still_scans(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "reply.json"
    body.write_text('{"body": "## Summary\\nFixed."}', encoding="utf-8")
    payload = tool_use(
        "Bash",
        {"command": f'gh api {REPLY_ENDPOINT} -X POST --input {body} --header "x'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(result)
    assert "SLOP014" in stderr


def test_malformed_json_payload_falls_back_to_the_raw_text(
    tool_use, run_hook, tmp_path
):
    # Arrange
    body = tmp_path / "reply.json"
    body.write_text('{"body": }\n## Summary of the fix\n', encoding="utf-8")
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPLY_ENDPOINT} -X POST --input {body}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(result)
    assert "SLOP014" in stderr


def test_payload_without_a_body_key_falls_back(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "reply.json"
    body.write_text('{"in_reply_to": 9981}', encoding="utf-8")
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPLY_ENDPOINT} -X POST --input {body}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_non_string_command_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": 12})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
