from __future__ import annotations

import json

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _pcd_support import (
    HOOK,
    REPO,
)


@pytest.mark.parametrize(
    "command",
    [
        'gh pr comment 12 --body "Fixed in a1b2c3d."',
        "GH_TOKEN=$(gh auth token --user alice) gh pr comment 12 --body-file /tmp/x.md",
        "gh pr comment https://github.com/acme/widgets/pull/12 -b hi",
    ],
)
def test_blocks_pr_conversation_comment(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC001")


def test_blocks_review_with_body_flag(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": 'gh pr review 12 --request-changes --body "Overall this needs work."'
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC002")


def test_blocks_review_with_body_file_flag(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr review 12 --comment --body-file /tmp/summary.md"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC002")


def test_allows_review_event_without_body(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "gh pr review 12 --approve"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_reviews_post_with_nonempty_body(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "review.json"
    body.write_text(
        json.dumps(
            {
                "commit_id": "a1b2c3d",
                "event": "REQUEST_CHANGES",
                "body": "Overall review summary",
                "comments": [{"path": "src/a.ts", "line": 4, "body": "off by one"}],
            }
        ),
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/reviews -X POST --input {body}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC003")


def test_allows_reviews_post_with_empty_body(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "review.json"
    body.write_text(
        json.dumps(
            {
                "commit_id": "a1b2c3d",
                "event": "REQUEST_CHANGES",
                "body": "",
                "comments": [{"path": "src/a.ts", "line": 4, "body": "off by one"}],
            }
        ),
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


def test_blocks_standalone_review_comment(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "comment.json"
    body.write_text(
        json.dumps({"path": "src/a.ts", "line": 4, "body": "off by one"}),
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/comments -X POST --input {body}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC004")


def test_allows_review_comment_with_in_reply_to(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "comment.json"
    body.write_text(
        json.dumps({"in_reply_to": 9981, "body": "Fixed in a1b2c3d."}),
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/comments -X POST --input {body}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_thread_reply_endpoint(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "reply.json"
    body.write_text(json.dumps({"body": "Fixed in a1b2c3d."}), encoding="utf-8")
    payload = tool_use(
        "Bash",
        {
            "command": (
                f"GH_TOKEN=$(gh auth token --user alice) gh api "
                f"{REPO}/pulls/12/comments/9981/replies -X POST --input {body}"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_issue_comments_endpoint(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/issues/12/comments -X POST -f body=ping"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC005")


def test_allows_gh_issue_comment_subcommand(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh issue comment 12 --body "Repro is in the description."'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
