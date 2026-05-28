"""Coverage for ai-process-leak-blocker hook.

Source rule: `~/.claude/rules/no-ai-process-leak.md`.
"""

from __future__ import annotations

import pytest

HOOK = "ai-process-leak-blocker"


@pytest.mark.parametrize(
    "phrase",
    [
        "Phase 1: initial scaffolding",
        "phase 12 of the work",
        "PHASE 0",
    ],
)
def test_blocks_phase_n_in_commit(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "{phrase}"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "Phase")


@pytest.mark.parametrize(
    "phrase",
    [
        "completed all the work of the plan",
        "implemented per the plan",
        "step 3 in the plan",
        "next item per the regnant plan",
    ],
)
def test_blocks_of_the_plan_references(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "{phrase}"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_refs_specs_trailer(tool_use, assert_blocks):
    # Arrange
    body = "Implements the feature.\n\nRefs: specs/2026-01-01-foo/plan.md"
    payload = tool_use(
        "Bash",
        {"command": f'gh pr create --title "feat" --body "{body}"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "Refs: specs/")


def test_blocks_plan_md_reference(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "see /specs/foo/plan.md for context"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "plan.md")


def test_blocks_spec_folder_mention(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "create spec folder for the work"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "spec folder")


def test_blocks_canvas_region(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "maps to canvas region 3"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "canvas region")


def test_blocks_state_of_the_art(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "introduces state-of-the-art parser"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_faithful_hyperbole(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "100% faithful port from spec"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "faithful")


def test_blocks_adr_reference(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "implements ADR-0012"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "ADR-0012")


def test_blocks_lands_in_phase(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "feature lands in phase 4"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_following_the_plan(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "following the plan from yesterday"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_gh_pr_create_with_leak(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh pr create --title "feat" --body "Phase 2 of the plan"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "Phase")


def test_blocks_gh_pr_edit_with_leak(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh pr edit 42 --body "Phase 3"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_gh_release_create(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh release create v1.0 --notes "Phase 1 ships"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_gh_issue_create(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh issue create --title "bug" --body "from Phase 5"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_glab_mr_create(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'glab mr create --description "Phase 2 work"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_git_tag_with_message(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git tag v1.0 -m "Phase 4 milestone"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_write_to_source_file(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// Phase 2 implementation\nfunction f() {}\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "Phase")


def test_blocks_edit_with_leak(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/app.ts",
            "old_string": "old",
            "new_string": "// Following the plan\nconst x = 1;",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_multiedit_with_leak(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/app.ts",
            "edits": [
                {"old_string": "a", "new_string": "// Phase 9"},
                {"old_string": "b", "new_string": "clean"},
            ],
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_allows_clean_commit(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "fix race condition in createUser"'},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_non_publishing_bash(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "echo Phase 1 of the plan"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_write_to_planning_artifact(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/specs/2026-01-01-foo/plan.md",
            "content": "# Phase 1: scaffolding\n\nMaps to canvas region 2.\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_write_to_adr(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/docs/adr/0012-foo.md",
            "content": "# ADR-0012\n\nSupersedes ADR-0008.\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_write_to_runbook(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/docs/runbook/incidents.md",
            "content": "# Incident phases\n\nPhase 1: detect.\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_write_to_claude_config(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/x/.claude/rules/my-rule.md",
            "content": "# Rule\n\nPhase 1 of the plan is fine here.\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_bypass_env_var_allows(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "Phase 1 of the plan"'},
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"AI_PROCESS_LEAK_DISABLE": "1"})


def test_allows_clean_pr_body(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh pr create --title "feat" --body "Adds a new endpoint for X"'},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_invalid_json_returns_zero():
    # Arrange
    import subprocess
    import sys
    from pathlib import Path

    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "ai-process-leak-blocker.py"
    )

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
    )

    # Assert
    assert proc.returncode == 0


def test_allows_unknown_tool(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/src/app.ts"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_empty_bash(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_state_of_the_art_in_docs(tool_use, assert_allows):
    # Arrange
    # Write to .claude tree, which is skipped
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/.claude/notes.md",
            "content": "Researching state-of-the-art parsers.",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_write_with_empty_path_still_checked(tool_use, assert_blocks):
    # Arrange: empty file_path triggers the early-return branch in is_skipped_path,
    # which means the content is still checked for leaks.
    payload = tool_use(
        "Write",
        {
            "file_path": "",
            "content": "Phase 1 of the plan",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_write_with_no_path_still_checked(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {"content": "Phase 7 work"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_multiedit_with_non_dict_edit(tool_use, assert_allows):
    # Arrange: edits entry that is not a dict gets skipped
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/app.ts",
            "edits": ["not-a-dict", {"old_string": "a", "new_string": "clean"}],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_blocks_gh_pr_body_file_with_leak(tmp_path, tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "spec folder")


def test_blocks_gh_pr_body_file_with_equals_form(tmp_path, tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_glab_description_file_with_leak(tmp_path, tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "Refs: specs/")


def test_blocks_gh_release_notes_file_with_leak(tmp_path, tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_allows_gh_pr_body_file_when_clean(tmp_path, tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_when_body_file_missing(tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_write_non_string_content_is_skipped(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": 12345},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


@pytest.mark.parametrize(
    "phrase",
    [
        "I ran the suite and it passed",
        "i ran the tests locally",
        "I ran jest on the affected files",
        "I ran the full suite three times",
    ],
)
def test_blocks_verification_loop_narration(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "fix bug. {phrase}"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "verification loop")


@pytest.mark.parametrize(
    "phrase",
    [
        "observed the actual status 500",
        "observed the behavior under load",
        "Observed the response shape",
    ],
)
def test_blocks_observed_narration(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "pin assertions. {phrase}"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "Empirical-observation narration")


def test_blocks_for_each_case_i_ran(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                'git commit -m "for each previously-permissive case I ran the assert"'
            )
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "Meta-iteration")


def test_blocks_pinned_to_match(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                'gh pr edit 42 --body "Pinned tests, with the asserts pinned to match the actual response"'
            )
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "verification as the deliverable")


@pytest.mark.parametrize(
    "phrase",
    [
        "All 21 tests still pass",
        "All 102 integration tests pass",
        "All 4 unit tests still passed",
    ],
)
def test_blocks_all_n_tests_pass_trailer(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'gh pr comment 42 --body "Fixed. {phrase}"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "Verification-summary trailer")


def test_blocks_gh_pr_comment_with_leak(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh pr comment 99 --body "Phase 2 work landed"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "Phase")


def test_blocks_gh_api_review_reply_input_file(tmp_path, tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "verification loop")


def test_blocks_gh_api_review_edit_patch_with_trailer(
    tmp_path, tool_use, assert_blocks
):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "Verification-summary trailer")


def test_allows_gh_api_review_reply_when_clean(tmp_path, tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_blocks_glab_mr_note_with_leak(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": ('glab mr note 42 --message "Following the plan, pushed the fix"')},
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_allows_human_phrasing_about_tests(tool_use, assert_allows):
    # Arrange
    # A normal "ran ... locally" mention without the verification-loop
    # framing should not trip the hook. The blocked phrase is specifically
    # "I ran the suite/tests/jest" as a methodical narration.
    payload = tool_use(
        "Bash",
        {
            "command": (
                'git commit -m "fix race in createUser; covered by an integration test"'
            )
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)
