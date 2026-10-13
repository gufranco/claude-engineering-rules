from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

from _helpers.cov_env import apply_coverage_env  # noqa: E402

HOOK = "ai-process-leak-blocker"


@pytest.mark.parametrize(
    "phrase",
    [
        "Phase 1: initial scaffolding",
        "phase 12 of the work",
        "PHASE 0",
    ],
)
def test_blocks_phase_n_in_commit(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "{phrase}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Phase")


@pytest.mark.parametrize(
    "phrase",
    [
        "completed all the work of the plan",
        "implemented per the plan",
        "step 3 in the plan",
        "next item per the regnant plan",
    ],
)
def test_blocks_of_the_plan_references(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "{phrase}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_allows_a_search_whose_quoted_pattern_names_a_publishing_command(
    tool_use, run_hook
):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": "grep -n 'gh pr create' skills/ship/SKILL.md "
            "specs/current/pr-comments/spec.md"
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_a_quoted_body_on_a_real_publishing_command(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr create --body 'Refs: specs/2026-01-01-foo/plan.md'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_blocks_refs_specs_trailer(tool_use, run_hook):
    # Arrange
    body = "Implements the feature.\n\nRefs: specs/2026-01-01-foo/plan.md"
    payload = tool_use(
        "Bash",
        {"command": f'gh pr create --title "feat" --body "{body}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Refs: specs/")


def test_blocks_plan_md_reference(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "see /specs/foo/plan.md for context"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "plan.md")


def test_blocks_spec_folder_mention(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "create spec folder for the work"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "spec folder")


def test_blocks_canvas_region(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "maps to canvas region 3"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "canvas region")


def test_blocks_state_of_the_art(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "introduces state-of-the-art parser"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_blocks_faithful_hyperbole(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "100% faithful port from spec"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "faithful")


def test_blocks_adr_reference(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "implements ADR-0012"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "ADR-0012")


def test_blocks_lands_in_phase(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "feature lands in phase 4"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_blocks_following_the_plan(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "following the plan from yesterday"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_blocks_gh_pr_create_with_leak(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh pr create --title "feat" --body "Phase 2 of the plan"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Phase")


def test_blocks_gh_pr_edit_with_leak(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh pr edit 42 --body "Phase 3"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_blocks_gh_release_create(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh release create v1.0 --notes "Phase 1 ships"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_blocks_gh_issue_create(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh issue create --title "bug" --body "from Phase 5"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_blocks_glab_mr_create(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'glab mr create --description "Phase 2 work"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_blocks_git_tag_with_message(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git tag v1.0 -m "Phase 4 milestone"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_blocks_write_to_source_file(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// Phase 2 implementation\nfunction f() {}\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Phase")


def test_blocks_edit_with_leak(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/app.ts",
            "old_string": "old",
            "new_string": "// Following the plan\nconst x = 1;",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_blocks_multiedit_with_leak(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_allows_clean_commit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "fix race condition in createUser"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_non_publishing_bash(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "echo Phase 1 of the plan"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_write_to_planning_artifact(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/specs/2026-01-01-foo/plan.md",
            "content": "# Phase 1: scaffolding\n\nMaps to canvas region 2.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_write_to_adr(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/docs/adr/0012-foo.md",
            "content": "# ADR-0012\n\nSupersedes ADR-0008.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_write_to_runbook(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/docs/runbook/incidents.md",
            "content": "# Incident phases\n\nPhase 1: detect.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_write_to_claude_config(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/x/.claude/rules/my-rule.md",
            "content": "# Rule\n\nPhase 1 of the plan is fine here.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_bypass_env_var_allows(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "Phase 1 of the plan"'},
    )

    # Act
    result = run_hook(HOOK, payload, env={"AI_PROCESS_LEAK_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_allows_clean_pr_body(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh pr create --title "feat" --body "Adds a new endpoint for X"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_invalid_json_blocks():
    # Arrange
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
        timeout=30,
        env={
            **os.environ,
            "CLAUDE_HOOK_AUDIT_DISABLE": "1",
            "CLAUDE_BYPASS_STATE": os.devnull,
        },
    )

    # Assert
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr


def test_allows_unknown_tool(tool_use, run_hook):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/src/app.ts"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_empty_bash(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_state_of_the_art_in_docs(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/.claude/notes.md",
            "content": "Researching state-of-the-art parsers.",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_with_empty_path_still_checked(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "",
            "content": "Phase 1 of the plan",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_write_with_no_path_still_checked(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"content": "Phase 7 work"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )


def test_multiedit_with_non_dict_edit_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/app.ts",
            "edits": ["not-a-dict", {"old_string": "a", "new_string": "clean"}],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: ai-process-leak-blocker could not read its input: tool_input.edits is not a",
    )


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


GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
PLANNING_TEXT = "# Phase 1: scaffolding\n\nMaps to canvas region 2.\n"


def make_repo(root: Path) -> Path:
    subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=root,
        check=True,
        capture_output=True,
        env={**os.environ, **GIT_ENV},
        timeout=30,
    )
    return root


def write_payload(tool_use, path: Path) -> dict:
    return tool_use("Write", {"file_path": str(path), "content": PLANNING_TEXT})


def test_allows_write_into_the_local_workspace(tool_use, run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path)
    target = repo / "docs" / "plans" / "x" / "plan.md"

    # Act
    result = run_hook(HOOK, write_payload(tool_use, target), env=GIT_ENV)

    # Assert
    assert_allowed(result)


def test_allows_write_into_the_fallback_workspace(tool_use, run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "index.md").write_text("# Project docs\n")
    target = repo / ".work" / "PROMPT.md"

    # Act
    result = run_hook(HOOK, write_payload(tool_use, target), env=GIT_ENV)

    # Assert
    assert_allowed(result)


def test_blocks_write_into_a_project_owned_docs(tool_use, run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "index.md").write_text("# Project docs\n")
    target = repo / "docs" / "guide.md"

    # Act
    result = run_hook(HOOK, write_payload(tool_use, target), env=GIT_ENV)

    # Assert
    assert_blocked(result, "Phase")


def test_blocks_write_outside_a_repository(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "docs" / "notes.md"

    # Act
    result = run_hook(HOOK, write_payload(tool_use, target), env=GIT_ENV)

    # Assert
    assert_blocked(result, "Phase")


def test_blocks_workspace_write_when_git_is_missing(tool_use, run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path)
    target = repo / "docs" / "PROMPT.md"
    env = {**GIT_ENV, "PATH": str(tmp_path / "empty")}

    # Act
    result = run_hook(HOOK, write_payload(tool_use, target), env=env)

    # Assert
    assert_blocked(result, "Phase")


@pytest.mark.parametrize(
    "message",
    [
        "Context lives in docs/PROMPT.md",
        "see .work/plans/2026-09-30-x for details",
        "details in ./docs/plans/",
    ],
)
def test_blocks_a_commit_naming_the_workspace(tool_use, run_hook, message):
    # Arrange
    payload = tool_use("Bash", {"command": f'git commit -m "{message}"'})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "workspace")


def test_allows_a_commit_naming_project_docs(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": 'git commit -m "docs: update docs/api.md"'})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_a_quoted_body_file_with_a_leak(tmp_path, tool_use, run_hook):
    # Arrange
    body = tmp_path / "body.md"
    body.write_text("Phase 3 landed.\n", encoding="utf-8")
    command = f"gh pr create --title fix --body-file '{body}'"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Phase")


def test_allows_an_empty_body_file_value(tool_use, run_hook):
    # Arrange
    command = "gh pr create --title fix --body-file ''"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.skipif(
    os.geteuid() == 0, reason="root reads files without permission bits"
)
def test_allows_an_unreadable_body_file(tmp_path, tool_use, run_hook):
    # Arrange
    body = tmp_path / "locked.md"
    body.write_text("Phase 3 landed.\n", encoding="utf-8")
    body.chmod(0)
    command = f"gh pr create --title fix --body-file {body}"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_edit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use("Edit", {"file_path": "/repo/src/app.ts", "new_string": 7})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: ai-process-leak-blocker could not read its input: tool_input.new_string is not",
    )


def test_multiedit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    edits = [{"old_string": "a", "new_string": 7}, "not an edit"]
    payload = tool_use("MultiEdit", {"file_path": "/repo/src/app.ts", "edits": edits})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: ai-process-leak-blocker could not read its input: tool_input.edits is not a",
    )


def test_malformed_payload_blocks():
    # Arrange
    hook = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input="not json",
        capture_output=True,
        text=True,
        env=apply_coverage_env({**os.environ, "CLAUDE_BYPASS_STATE": os.devnull}),
        check=False,
        timeout=30,
    )

    # Assert
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr
