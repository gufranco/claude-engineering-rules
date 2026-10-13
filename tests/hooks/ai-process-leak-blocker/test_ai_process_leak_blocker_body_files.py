from __future__ import annotations


import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked


HOOK = "ai-process-leak-blocker"


def test_blocks_gh_pr_body_file_with_leak(tmp_path, tool_use, run_hook):
    # Arrange
    body = tmp_path / "pr-body.md"
    body.write_text(
        "## Follow-ups\n\nThe spec folder lists more notes.\n",
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": (f"gh pr create --base develop --title hello --body-file {body}")},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "spec folder")


def test_blocks_gh_pr_body_file_with_equals_form(tmp_path, tool_use, run_hook):
    # Arrange
    body = tmp_path / "pr-body.md"
    body.write_text(
        "Implements per the plan.\n",
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": f"gh pr edit 1234 --body-file={body}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_blocks_glab_description_file_with_leak(tmp_path, tool_use, run_hook):
    # Arrange
    body = tmp_path / "mr-body.md"
    body.write_text(
        "Refs: specs/2026-01-01-foo/plan.md\n",
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": (f"glab mr create --description-file {body}")},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Refs: specs/")


def test_blocks_gh_release_notes_file_with_leak(tmp_path, tool_use, run_hook):
    # Arrange
    body = tmp_path / "notes.md"
    body.write_text(
        "Phase 1 of the rollout.\n",
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": (f"gh release create v1.0.0 --notes-file {body}")},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_allows_gh_pr_body_file_when_clean(tmp_path, tool_use, run_hook):
    # Arrange
    body = tmp_path / "pr-body.md"
    body.write_text(
        "## What\n\nFix race condition in createUser.\n",
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": (f"gh pr create --base develop --title fix --body-file {body}")},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_when_body_file_missing(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                "gh pr create --base develop --title fix"
                " --body-file /tmp/definitely-not-there.md"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_non_string_content_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": 12345},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: ai-process-leak-blocker could not read its input: tool_input.content is not a",
    )


@pytest.mark.parametrize(
    "phrase",
    [
        "I ran the suite and it passed",
        "i ran the tests locally",
        "I ran jest on the affected files",
        "I ran the full suite three times",
    ],
)
def test_blocks_verification_loop_narration(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "fix bug. {phrase}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "verification loop")


@pytest.mark.parametrize(
    "phrase",
    [
        "observed the actual status 500",
        "observed the behavior under load",
        "Observed the response shape",
    ],
)
def test_blocks_observed_narration(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "pin assertions. {phrase}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Empirical-observation narration")


def test_blocks_for_each_case_i_ran(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                'git commit -m "for each previously-permissive case I ran the assert"'
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Meta-iteration")


def test_blocks_pinned_to_match(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                'gh pr edit 42 --body "Pinned tests, with the asserts pinned to match the actual response"'
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "verification as the deliverable")


@pytest.mark.parametrize(
    "phrase",
    [
        "All 21 tests still pass",
        "All 102 integration tests pass",
        "All 4 unit tests still passed",
    ],
)
def test_blocks_all_n_tests_pass_trailer(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'gh pr comment 42 --body "Fixed. {phrase}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Verification-summary trailer")


def test_blocks_gh_pr_comment_with_leak(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh pr comment 99 --body "Phase 2 work landed"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Phase")


def test_blocks_gh_api_review_reply_input_file(tmp_path, tool_use, run_hook):
    # Arrange
    body = tmp_path / "reply.json"
    body.write_text(
        '{"body": "Pinned. I ran the suite and observed the actual status."}',
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {
            "command": (
                "gh api repos/o/r/pulls/1779/comments/12345/replies"
                f" -X POST --input {body}"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "verification loop")


def test_blocks_gh_api_review_edit_patch_with_trailer(tmp_path, tool_use, run_hook):
    # Arrange
    body = tmp_path / "edit.json"
    body.write_text(
        '{"body": "Fixed in 597d6d1c. All 21 redemption integration tests still pass."}',
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {"command": (f"gh api repos/o/r/pulls/comments/12345 -X PATCH --input {body}")},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Verification-summary trailer")


def test_allows_gh_api_review_reply_when_clean(tmp_path, tool_use, run_hook):
    # Arrange
    body = tmp_path / "reply.json"
    body.write_text(
        '{"body": "Pinned to 200 with empty array. The fixture seeds an empty store."}',
        encoding="utf-8",
    )
    payload = tool_use(
        "Bash",
        {
            "command": (
                "gh api repos/o/r/pulls/1779/comments/12345/replies"
                f" -X POST --input {body}"
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_glab_mr_note_with_leak(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": ('glab mr note 42 --message "Following the plan, pushed the fix"')},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_allows_human_phrasing_about_tests(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                'git commit -m "fix race in createUser; covered by an integration test"'
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_project_vocabulary_inside_the_second_brain_vault(
    tool_use, run_hook, tmp_path
):
    # Arrange
    vault = tmp_path / "vault" / "wiki" / "projects"
    vault.mkdir(parents=True)
    payload = tool_use(
        "Write",
        {
            "file_path": str(vault / "Rollout.md"),
            "content": "Phase 2 of the rollout is done. I ran the suite and all 12 tests pass.\n",
        },
    )

    # Act
    result = run_hook(
        HOOK, payload, env={"SECOND_BRAIN_VAULT": str(tmp_path / "vault")}
    )

    # Assert
    assert_allowed(result)


def test_still_blocks_process_language_outside_the_vault(tool_use, run_hook, tmp_path):
    # Arrange
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "project" / "README.md"
    outside.parent.mkdir()
    payload = tool_use(
        "Write",
        {
            "file_path": str(outside),
            "content": "Phase 2 of the rollout is done. I ran the suite and all 12 tests pass.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"SECOND_BRAIN_VAULT": str(vault)})

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )
