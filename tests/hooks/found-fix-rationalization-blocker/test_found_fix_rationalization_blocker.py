from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "found-fix-rationalization-blocker"


@pytest.mark.parametrize(
    "phrase",
    [
        "Annotation is not introduced by this PR",
        "deprecation not introduced by this change",
        "not introduced by this task",
        "Not introduced by my commit",
        "not introduced by the work",
        "Not Introduced By This Patch",
    ],
)
def test_blocks_not_introduced_in_commit(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "fix: bump - {phrase}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "not introduced")


@pytest.mark.parametrize(
    "phrase",
    [
        "Pre-existing, not mine",
        "preexisting concern, not in scope",
        "pre-existing, not introduced",
        "pre-existing - not from this PR",
    ],
)
def test_blocks_pre_existing_inaction(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "fix: bump - {phrase}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "pre-existing")


@pytest.mark.parametrize(
    "phrase",
    [
        "Orthogonal to this task",
        "orthogonal to the work",
        "Orthogonal To This PR",
    ],
)
def test_blocks_orthogonal_inaction(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "fix: bump - {phrase}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "orthogonal")


@pytest.mark.parametrize(
    "phrase",
    [
        "out of scope of this task",
        "out of scope for this PR",
        "out of scope of the change",
    ],
)
def test_blocks_out_of_scope_inaction(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "fix: bump - {phrase}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "out of scope")


@pytest.mark.parametrize(
    "phrase",
    [
        "leave for later",
        "leave this for later",
        "leave for a future task",
        "leave for the next PR",
        "leave it for follow-up",
    ],
)
def test_blocks_leave_for_later(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "fix: bump - {phrase}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_blocks_not_blocking_the_run(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "fix - Not blocking the run"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "not blocking")


def test_blocks_in_pr_create_body(tool_use, run_hook):
    # Arrange
    body = "Upgrades action X. Deprecation will be addressed later."
    payload = tool_use(
        "Bash",
        {"command": f'gh pr create --title "chore" --body "{body}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "addressed later")


def test_blocks_in_gh_release_create(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh release create v1.0 --notes "Not introduced by this PR"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_blocks_in_write_payload_to_code(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "module.py"
    payload = tool_use(
        "Write",
        {
            "file_path": str(target),
            "content": "# Not introduced by this PR. We will fix later.\nx = 1\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_allows_clean_commit_message(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "fix: upgrade action X to clear deprecation"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_non_publishing_bash_with_phrase(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'grep -r "not introduced by this PR" .'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_history_use_of_pre_existing(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "docs: explain pre-existing test fixture"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_history_use_of_orthogonal(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "refactor: separate orthogonal concerns"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_write_to_rule_file(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "rules" / "found-fix.md"
    target.parent.mkdir(parents=True)
    payload = tool_use(
        "Write",
        {
            "file_path": str(target),
            "content": "Bans 'not introduced by this PR' and 'orthogonal to this task'.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_bypass_env(monkeypatch, tool_use, run_hook):
    # Arrange
    monkeypatch.setenv("FOUND_FIX_RATIONALIZATION_DISABLE", "1")
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "fix - Not introduced by this PR"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "phrase",
    [
        "Filed as ENG-1234 to track the rest",
        "filed an issue for the remaining path",
        "Opened an issue for the second helper",
        "tracked in ENG-1235",
        "Tracking in a ticket",
    ],
)
def test_blocks_tracker_item_standing_in_for_a_fix(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "fix: guard the null path" -m "{phrase}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "tracker")


@pytest.mark.parametrize(
    "phrase",
    [
        "will follow up in a separate PR",
        "Will fix in a follow-up PR",
        "fixing the rest in a separate change",
        "addressing the duplicate in a follow-up commit",
    ],
)
def test_blocks_follow_up_change_standing_in_for_a_fix(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "fix: guard the null path" -m "{phrase}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "follow-up change")


@pytest.mark.parametrize(
    "phrase",
    [
        "Fixed the null path and the duplicate in the same pass",
        "Closes ENG-1234",
        "Refs ENG-1235",
        "Follows the pattern in orderService",
        "A bot opened a thread naming a genuine bug",
        "The reviewer raised a real concern about the lock",
        "Tracking the retry budget in a counter",
    ],
)
def test_allows_ordinary_artifact_text(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "fix: guard the null path" -m "{phrase}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
