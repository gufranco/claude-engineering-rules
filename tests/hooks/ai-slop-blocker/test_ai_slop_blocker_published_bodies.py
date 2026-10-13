from __future__ import annotations


import sys
from pathlib import Path

from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "ai-slop-blocker"
DOC = "/repo/docs/notes.md"

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))


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
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
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
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
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
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
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
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
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
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
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
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
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
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
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
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
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
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
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


def test_non_string_command_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": 12})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: ai-slop-blocker could not read its input: tool_input.command is not a string.",
    )
