from __future__ import annotations

import json

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "pr-comment-discipline"
REPO = "repos/acme/widgets"


@pytest.mark.parametrize(
    "command",
    [
        "gh pr review 12 --comment -b 'summary text'",
        "gh pr review 12 --comment -b='summary text'",
        "gh pr review 12 --comment -F notes.md",
        "gh pr review 12 --approve --body-file=notes.md",
    ],
)
def test_a_review_body_in_any_flag_form_blocks(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC002")


def test_a_bodyless_review_next_to_another_command_passes(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash", {"command": "gh pr review 12 --approve && gh api user -F x=1"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_review_body_sent_as_a_typed_field_blocks(tool_use, run_hook):
    # Arrange
    command = (
        f"gh api {REPO}/pulls/1/reviews -X POST -f event=COMMENT -F body=@notes.md"
    )
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC003")


@pytest.mark.parametrize("separator", [" ; ", " && ", "\n"])
def test_a_reply_does_not_exempt_a_second_comment_post(
    tool_use, run_hook, tmp_path, separator
):
    # Arrange
    reply = tmp_path / "reply.json"
    reply.write_text(json.dumps({"body": "Fixed in a1b2c3d."}), encoding="utf-8")
    first = f"gh api {REPO}/pulls/1/comments/9/replies -X POST --input {reply}"
    second = f"gh api {REPO}/issues/1/comments -X POST -f body=hello"
    payload = tool_use("Bash", {"command": first + separator + second})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC005")


def test_a_relative_payload_file_is_read_from_the_session_directory(
    tool_use, run_hook, tmp_path
):
    # Arrange
    (tmp_path / "review.json").write_text(
        json.dumps({"event": "COMMENT", "body": "Summary of the review."}),
        encoding="utf-8",
    )
    command = f"gh api {REPO}/pulls/1/reviews -X POST --input review.json"
    payload = tool_use("Bash", {"command": command}, cwd=str(tmp_path))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC003")


def test_an_empty_review_body_in_a_relative_file_passes(tool_use, run_hook, tmp_path):
    # Arrange
    (tmp_path / "review.json").write_text(
        json.dumps({"event": "COMMENT", "body": "", "comments": []}),
        encoding="utf-8",
    )
    command = f"gh api {REPO}/pulls/1/reviews -X POST --input review.json"
    payload = tool_use("Bash", {"command": command}, cwd=str(tmp_path))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
