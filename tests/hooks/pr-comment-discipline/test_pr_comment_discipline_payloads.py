from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked
from _pcd_support import (
    HOOK,
    REPO,
)


def test_a_missing_review_payload_file_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                f"gh api {REPO}/pulls/12/reviews -X POST "
                "--input /tmp/definitely-not-there-9f3a.json"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC010")


def test_unbalanced_json_in_payload_uses_the_text_fallback(
    tool_use, run_hook, tmp_path
):
    # Arrange
    body = tmp_path / "broken.json"
    body.write_text('{"body": "Overall summary", "comments": [', encoding="utf-8")
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/reviews -X POST --input {body}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC003")


def test_field_flag_body_counts_as_a_summary(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                f"gh api {REPO}/pulls/12/reviews -X POST "
                "-f event=COMMENT -f body=Overall"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC003")


def test_empty_field_flag_body_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                f"gh api {REPO}/pulls/12/reviews -X POST -f event=APPROVE -f body="
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_json_array_payload_is_not_a_body(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "reply.json"
    body.write_text('[{"in_reply_to": 9981}]', encoding="utf-8")
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/comments -X POST --input {body}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_profile_disable_skips_the_hook(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": 'gh pr comment 12 --body "hi"'})

    # Act
    result = run_hook(
        HOOK, payload, env={"CLAUDE_DISABLED_HOOKS": "pr-comment-discipline"}
    )

    # Assert
    assert_allowed(result)


def test_empty_command_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_an_unreadable_review_payload_path_blocks(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/reviews -X POST --input {tmp_path}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC010")


def test_unparseable_command_still_reads_the_payload_file(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "review.json"
    body.write_text('{"event": "COMMENT", "body": "Summary."}', encoding="utf-8")
    payload = tool_use(
        "Bash",
        {
            "command": (
                f'gh api {REPO}/pulls/12/reviews -X POST --input {body} --header "x'
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC003")


def test_invalid_json_object_uses_the_text_fallback(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "review.json"
    body.write_text('{"body": } {"body": "Summary."}', encoding="utf-8")
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/reviews -X POST --input {body}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC003")


def test_payload_without_a_body_key_is_allowed(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "review.json"
    body.write_text('{"event": "APPROVE"}', encoding="utf-8")
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/reviews -X POST --input {body}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_braces_inside_a_comment_body_are_not_a_summary(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "review.json"
    body.write_text(
        '{"event": "COMMENT", "body": "", "comments": [{"path": "a.ts", '
        '"line": 1, "body": "```suggestion\\n  if (x) { y }\\n```"}]}',
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/reviews -X POST --input {body}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
