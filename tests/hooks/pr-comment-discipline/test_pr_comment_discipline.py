"""Coverage for the pr-comment-discipline hook.

Source rule: `~/.claude/rules/pr-comment-discipline.md`.
"""

from __future__ import annotations

import json

import pytest

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
def test_blocks_pr_conversation_comment(tool_use, assert_blocks, command):
    payload = tool_use("Bash", {"command": command})

    assert_blocks(HOOK, payload, "PRC001")


def test_blocks_review_with_body_flag(tool_use, assert_blocks):
    payload = tool_use(
        "Bash",
        {
            "command": 'gh pr review 12 --request-changes --body "Overall this needs work."'
        },
    )

    assert_blocks(HOOK, payload, "PRC002")


def test_blocks_review_with_body_file_flag(tool_use, assert_blocks):
    payload = tool_use(
        "Bash",
        {"command": "gh pr review 12 --comment --body-file /tmp/summary.md"},
    )

    assert_blocks(HOOK, payload, "PRC002")


def test_allows_review_event_without_body(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "gh pr review 12 --approve"})

    assert_allows(HOOK, payload)


def test_blocks_reviews_post_with_nonempty_body(tool_use, assert_blocks, tmp_path):
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

    assert_blocks(HOOK, payload, "PRC003")


def test_allows_reviews_post_with_empty_body(tool_use, assert_allows, tmp_path):
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

    assert_allows(HOOK, payload)


def test_blocks_standalone_review_comment(tool_use, assert_blocks, tmp_path):
    body = tmp_path / "comment.json"
    body.write_text(
        json.dumps({"path": "src/a.ts", "line": 4, "body": "off by one"}),
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/comments -X POST --input {body}"},
    )

    assert_blocks(HOOK, payload, "PRC004")


def test_allows_review_comment_with_in_reply_to(tool_use, assert_allows, tmp_path):
    body = tmp_path / "comment.json"
    body.write_text(
        json.dumps({"in_reply_to": 9981, "body": "Fixed in a1b2c3d."}),
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/comments -X POST --input {body}"},
    )

    assert_allows(HOOK, payload)


def test_allows_thread_reply_endpoint(tool_use, assert_allows, tmp_path):
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

    assert_allows(HOOK, payload)


def test_blocks_issue_comments_endpoint(tool_use, assert_blocks):
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/issues/12/comments -X POST -f body=ping"},
    )

    assert_blocks(HOOK, payload, "PRC005")


def test_allows_gh_issue_comment_subcommand(tool_use, assert_allows):
    payload = tool_use(
        "Bash",
        {"command": 'gh issue comment 12 --body "Repro is in the description."'},
    )

    assert_allows(HOOK, payload)


def test_blocks_gitlab_mr_note(tool_use, assert_blocks):
    payload = tool_use(
        "Bash",
        {
            "command": (
                "GITLAB_TOKEN=$(glab auth token --hostname gitlab.com) "
                'glab mr note 12 --message "Fixed."'
            )
        },
    )

    assert_blocks(HOOK, payload, "PRC006")


def test_blocks_commit_comment(tool_use, assert_blocks):
    payload = tool_use(
        "Bash",
        {
            "command": (
                f"gh api {REPO}/commits/a1b2c3d4e5f6a7b8/comments -X POST -f body=note"
            )
        },
    )

    assert_blocks(HOOK, payload, "PRC007")


def test_blocks_new_gitlab_discussion(tool_use, assert_blocks):
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

    assert_blocks(HOOK, payload, "PRC008")


def test_allows_gitlab_discussion_note_reply(tool_use, assert_allows):
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

    assert_allows(HOOK, payload)


def test_blocks_bitbucket_parentless_comment(tool_use, assert_blocks, tmp_path):
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

    assert_blocks(HOOK, payload, "PRC009")


def test_allows_bitbucket_reply_with_parent(tool_use, assert_allows, tmp_path):
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

    assert_allows(HOOK, payload)


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
def test_allows_unrelated_and_read_only_commands(tool_use, assert_allows, command):
    payload = tool_use("Bash", {"command": command})

    assert_allows(HOOK, payload)


def test_allows_non_bash_tools(tool_use, assert_allows):
    payload = tool_use(
        "Write", {"file_path": "/tmp/x.md", "content": "gh pr comment 1"}
    )

    assert_allows(HOOK, payload)


def test_bypass_env_allows(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": 'gh pr comment 12 --body "hi"'})

    assert_allows(HOOK, payload, env={"PR_COMMENT_DISCIPLINE_DISABLE": "1"})


def test_malformed_payload_is_ignored(run_hook):
    code, _stdout, _stderr = run_hook(HOOK, {"tool_name": "Bash"})

    assert code == 0


def test_inline_heredoc_body_is_read(tool_use, assert_blocks):
    command = (
        f"gh api {REPO}/pulls/12/reviews -X POST --input - <<'JSON'\n"
        '{"event": "COMMENT", "body": "Nice work overall.", "comments": []}\n'
        "JSON"
    )
    payload = tool_use("Bash", {"command": command})

    assert_blocks(HOOK, payload, "PRC003")


def test_unparseable_quoting_still_blocks(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": 'gh pr comment 12 --body "unbalanced'})

    assert_blocks(HOOK, payload, "PRC001")


@pytest.mark.parametrize(
    "method_flag",
    [
        "--method POST",
        "--method=POST",
        "--request PUT",
        "-XPATCH",
    ],
)
def test_recognizes_every_method_spelling(tool_use, assert_blocks, method_flag):
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/issues/12/comments {method_flag}"},
    )

    assert_blocks(HOOK, payload, "PRC005")


def test_read_only_method_is_not_a_write(tool_use, assert_allows):
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/issues/12/comments --method GET"},
    )

    assert_allows(HOOK, payload)


def test_trailing_payload_flag_without_a_value(tool_use, assert_blocks):
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/comments -X POST --input"},
    )

    assert_blocks(HOOK, payload, "PRC004")


def test_stdin_payload_falls_back_to_the_command(tool_use, assert_blocks):
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/comments -X POST --input -"},
    )

    assert_blocks(HOOK, payload, "PRC004")


def test_missing_payload_file_reads_as_no_summary(tool_use, assert_allows):
    payload = tool_use(
        "Bash",
        {
            "command": (
                f"gh api {REPO}/pulls/12/reviews -X POST "
                "--input /tmp/definitely-not-there-9f3a.json"
            )
        },
    )

    assert_allows(HOOK, payload)


def test_unbalanced_json_in_payload_uses_the_text_fallback(
    tool_use, assert_blocks, tmp_path
):
    body = tmp_path / "broken.json"
    body.write_text('{"body": "Overall summary", "comments": [', encoding="utf-8")
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/reviews -X POST --input {body}"},
    )

    assert_blocks(HOOK, payload, "PRC003")


def test_field_flag_body_counts_as_a_summary(tool_use, assert_blocks):
    payload = tool_use(
        "Bash",
        {
            "command": (
                f"gh api {REPO}/pulls/12/reviews -X POST "
                "-f event=COMMENT -f body=Overall"
            )
        },
    )

    assert_blocks(HOOK, payload, "PRC003")


def test_empty_field_flag_body_is_allowed(tool_use, assert_allows):
    payload = tool_use(
        "Bash",
        {
            "command": (
                f"gh api {REPO}/pulls/12/reviews -X POST -f event=APPROVE -f body="
            )
        },
    )

    assert_allows(HOOK, payload)


def test_json_array_payload_is_not_a_body(tool_use, assert_allows, tmp_path):
    body = tmp_path / "reply.json"
    body.write_text('[{"in_reply_to": 9981}]', encoding="utf-8")
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/comments -X POST --input {body}"},
    )

    assert_allows(HOOK, payload)


def test_glab_read_of_discussions_is_allowed(tool_use, assert_allows):
    payload = tool_use(
        "Bash",
        {
            "command": (
                "GITLAB_TOKEN=$(glab auth token --hostname gitlab.com) glab api "
                "projects/acme%2Fwidgets/merge_requests/12/discussions"
            )
        },
    )

    assert_allows(HOOK, payload)


def test_curl_to_an_unrelated_endpoint_is_allowed(tool_use, assert_allows):
    payload = tool_use(
        "Bash",
        {
            "command": (
                "curl -s -X POST -d '{}' "
                "https://api.bitbucket.org/2.0/repositories/acme/widgets/pullrequests/12/approve"
            )
        },
    )

    assert_allows(HOOK, payload)


def test_profile_disable_skips_the_hook(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": 'gh pr comment 12 --body "hi"'})

    assert_allows(
        HOOK,
        payload,
        env={"CLAUDE_DISABLED_HOOKS": "pr-comment-discipline"},
    )


def test_empty_command_is_ignored(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": ""})

    assert_allows(HOOK, payload)


def test_unreadable_payload_path_falls_back(tool_use, assert_allows, tmp_path):
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/reviews -X POST --input {tmp_path}"},
    )

    assert_allows(HOOK, payload)


def test_unparseable_command_still_reads_the_payload_file(
    tool_use, assert_blocks, tmp_path
):
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

    assert_blocks(HOOK, payload, "PRC003")


def test_invalid_json_object_uses_the_text_fallback(tool_use, assert_blocks, tmp_path):
    body = tmp_path / "review.json"
    body.write_text('{"body": } {"body": "Summary."}', encoding="utf-8")
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/reviews -X POST --input {body}"},
    )

    assert_blocks(HOOK, payload, "PRC003")


def test_payload_without_a_body_key_is_allowed(tool_use, assert_allows, tmp_path):
    body = tmp_path / "review.json"
    body.write_text('{"event": "APPROVE"}', encoding="utf-8")
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/reviews -X POST --input {body}"},
    )

    assert_allows(HOOK, payload)


def test_glab_write_to_an_unrelated_endpoint_is_allowed(tool_use, assert_allows):
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

    assert_allows(HOOK, payload)
