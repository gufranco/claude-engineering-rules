"""Coverage for found-fix-rationalization-blocker hook.

Source rule: `~/.claude/rules/found-fix.md`.
"""

from __future__ import annotations

import pytest

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
def test_blocks_not_introduced_in_commit(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "fix: bump - {phrase}"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "not introduced")


@pytest.mark.parametrize(
    "phrase",
    [
        "Pre-existing, not mine",
        "preexisting concern, not in scope",
        "pre-existing, not introduced",
        "pre-existing - not from this PR",
    ],
)
def test_blocks_pre_existing_inaction(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "fix: bump - {phrase}"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "pre-existing")


@pytest.mark.parametrize(
    "phrase",
    [
        "Orthogonal to this task",
        "orthogonal to the work",
        "Orthogonal To This PR",
    ],
)
def test_blocks_orthogonal_inaction(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "fix: bump - {phrase}"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "orthogonal")


@pytest.mark.parametrize(
    "phrase",
    [
        "out of scope of this task",
        "out of scope for this PR",
        "out of scope of the change",
    ],
)
def test_blocks_out_of_scope_inaction(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "fix: bump - {phrase}"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "out of scope")


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
def test_blocks_leave_for_later(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f'git commit -m "fix: bump - {phrase}"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_not_blocking_the_run(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "fix - Not blocking the run"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "not blocking")


def test_blocks_in_pr_create_body(tool_use, assert_blocks):
    # Arrange
    body = "Upgrades action X. Deprecation will be addressed later."
    payload = tool_use(
        "Bash",
        {"command": f'gh pr create --title "chore" --body "{body}"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "addressed later")


def test_blocks_in_gh_release_create(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'gh release create v1.0 --notes "Not introduced by this PR"'},
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_in_write_payload_to_code(tool_use, assert_blocks, tmp_path):
    # Arrange: a code comment with rationalization wording
    target = tmp_path / "module.py"
    payload = tool_use(
        "Write",
        {
            "file_path": str(target),
            "content": "# Not introduced by this PR. We will fix later.\nx = 1\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_allows_clean_commit_message(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "fix: upgrade action X to clear deprecation"'},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_non_publishing_bash_with_phrase(tool_use, assert_allows):
    # Arrange: grep for the phrase in the repo is fine
    payload = tool_use(
        "Bash",
        {"command": 'grep -r "not introduced by this PR" .'},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_history_use_of_pre_existing(tool_use, assert_allows):
    # Arrange: "pre-existing" without an inaction trailing word is fine
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "docs: explain pre-existing test fixture"'},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_history_use_of_orthogonal(tool_use, assert_allows):
    # Arrange: "orthogonal" without the inaction object is fine
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "refactor: separate orthogonal concerns"'},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_write_to_rule_file(tool_use, assert_allows, tmp_path):
    # Arrange: editing the rule file itself is exempt
    target = tmp_path / "rules" / "found-fix.md"
    target.parent.mkdir(parents=True)
    payload = tool_use(
        "Write",
        {
            "file_path": str(target),
            "content": "Bans 'not introduced by this PR' and 'orthogonal to this task'.\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_bypass_env(monkeypatch, tool_use, assert_allows):
    # Arrange
    monkeypatch.setenv("FOUND_FIX_RATIONALIZATION_DISABLE", "1")
    payload = tool_use(
        "Bash",
        {"command": 'git commit -m "fix - Not introduced by this PR"'},
    )

    # Act / Assert
    assert_allows(HOOK, payload)
