from __future__ import annotations

import json

from _helpers.hook_assertions import assert_allowed, assert_blocked
from _pcd_support import (
    HOOK,
    REPO,
)


def test_blocks_gitlab_mr_note(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                "GITLAB_TOKEN=$(glab auth token --hostname gitlab.com) "
                'glab mr note 12 --message "Fixed."'
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC006")


def test_blocks_commit_comment(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                f"gh api {REPO}/commits/a1b2c3d4e5f6a7b8/comments -X POST -f body=note"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC007")


def test_blocks_new_gitlab_discussion(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                "GITLAB_TOKEN=$(glab auth token --hostname gitlab.com) glab api "
                "projects/acme%2Fwidgets/merge_requests/12/discussions "
                "-X POST --field body=hello"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC008")


def test_allows_gitlab_discussion_note_reply(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                "GITLAB_TOKEN=$(glab auth token --hostname gitlab.com) glab api "
                "projects/acme%2Fwidgets/merge_requests/12/discussions/abc123/notes "
                "-X POST --field body=Fixed"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_bitbucket_parentless_comment(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "bb.json"
    body.write_text(json.dumps({"content": {"raw": "Fixed."}}), encoding="utf-8")
    payload = tool_use(
        "Bash",
        {
            "command": (
                'curl -s -u "$BITBUCKET_USERNAME:$BITBUCKET_APP_PASSWORD" -X POST '
                '-H "Content-Type: application/json" '
                f"--data @{body} "
                "https://api.bitbucket.org/2.0/repositories/acme/widgets/"
                "pullrequests/12/comments"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC009")


def test_allows_bitbucket_reply_with_parent(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "bb.json"
    body.write_text(
        json.dumps({"content": {"raw": "Fixed."}, "parent": {"id": 77}}),
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {
            "command": (
                'curl -s -u "$BITBUCKET_USERNAME:$BITBUCKET_APP_PASSWORD" -X POST '
                f"--data @{body} "
                "https://api.bitbucket.org/2.0/repositories/acme/widgets/"
                "pullrequests/12/comments"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_glab_read_of_discussions_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                "GITLAB_TOKEN=$(glab auth token --hostname gitlab.com) glab api "
                "projects/acme%2Fwidgets/merge_requests/12/discussions"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_curl_to_an_unrelated_endpoint_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                "curl -s -X POST -d '{}' "
                "https://api.bitbucket.org/2.0/repositories/acme/widgets/pullrequests/12/approve"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_glab_write_to_an_unrelated_endpoint_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                "GITLAB_TOKEN=$(glab auth token --hostname gitlab.com) glab api "
                "projects/acme%2Fwidgets/merge_requests/12 -X PUT "
                "--field reviewer_ids[]=4"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
