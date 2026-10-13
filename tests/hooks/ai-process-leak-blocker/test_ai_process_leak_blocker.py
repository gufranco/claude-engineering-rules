from __future__ import annotations


import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked


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
