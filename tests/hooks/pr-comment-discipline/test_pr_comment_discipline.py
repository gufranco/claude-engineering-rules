from __future__ import annotations

import json

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "pr-comment-discipline"
REPO = "repos/acme/widgets"


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


@pytest.mark.parametrize(
    "command",
    [
        "gh pr edit 12 --body-file /tmp/description.md",
        "gh pr create --title fix --body-file /tmp/description.md",
        f"gh api {REPO}/pulls/12/comments",
        f"gh api {REPO}/issues/12/comments --paginate",
        "gh api graphql -f query='mutation { resolveReviewThread(input: {threadId: \"x\"}) { thread { id } } }'",
        "git commit -m 'fix: off by one'",
    ],
)
def test_allows_unrelated_and_read_only_commands(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_non_bash_tools(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/tmp/x.md", "content": "gh pr comment 1"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_bypass_env_allows(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": 'gh pr comment 12 --body "hi"'})

    # Act
    result = run_hook(HOOK, payload, env={"PR_COMMENT_DISCIPLINE_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_malformed_payload_is_ignored(run_hook):
    # Arrange
    payload = {"tool_name": "Bash"}

    # Act
    code, _stdout, _stderr = run_hook(HOOK, payload)

    # Assert
    assert code == 0


def test_inline_heredoc_body_is_read(tool_use, run_hook):
    # Arrange
    command = (
        f"gh api {REPO}/pulls/12/reviews -X POST --input - <<'JSON'\n"
        '{"event": "COMMENT", "body": "Nice work overall.", "comments": []}\n'
        "JSON"
    )
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC003")


def test_unparseable_quoting_still_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": 'gh pr comment 12 --body "unbalanced'})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC001")


@pytest.mark.parametrize(
    "method_flag",
    [
        "--method POST",
        "--method=POST",
        "--request PUT",
        "-XPATCH",
    ],
)
def test_recognizes_every_method_spelling(tool_use, run_hook, method_flag):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/issues/12/comments {method_flag}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC005")


def test_read_only_method_is_not_a_write(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/issues/12/comments --method GET"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "command",
    [
        f"ls -d node_modules && gh api {REPO}/pulls/12/comments",
        f"gh api {REPO}/pulls/12/comments | jq -f filter.jq",
        f"cut -d, -f1 ids.csv; gh api {REPO}/issues/12/comments",
    ],
)
def test_a_flag_from_another_command_is_not_a_payload(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    ("command", "code"),
    [
        (f"ls -d node_modules && gh api {REPO}/pulls/12/comments -f body=hi", "PRC004"),
        (f"cat body.json | gh api {REPO}/issues/12/comments --input -", "PRC005"),
        (f"cd repo; gh api {REPO}/pulls/12/comments -X POST", "PRC004"),
    ],
)
def test_a_write_chained_after_another_command_is_still_caught(
    tool_use, run_hook, command, code
):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, code)


def test_trailing_payload_flag_without_a_value(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/comments -X POST --input"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC004")


def test_stdin_payload_falls_back_to_the_command(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/comments -X POST --input -"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC004")


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
