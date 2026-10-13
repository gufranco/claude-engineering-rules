from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _icl_support import (
    HOOK,
)


def test_blocks_slack_send_with_category_reference(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "slack send 'review failed at category 5'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


def test_blocks_slack_cli_post(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "slack-cli post '#chan' 'see categories 12'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


def test_blocks_curl_to_slack(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": (
                "curl -X POST https://hooks.slack.com/x "
                '-d \'{"text": "category 12 failure"}\''
            )
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


def test_blocks_category_number_reference(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'Failed on category #3 checks'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "category number")


def test_blocks_cat_shorthand(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'See cat 12 of the review checklist'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "cat <n> shorthand")


def test_blocks_checklist_item_mention(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'Per checklist item 5 this fails'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "checklist")


def test_blocks_md_write_with_internal_path(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/docs/notes.md",
            "content": "Refer to $HOME/.claude/rules/security.md for details.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


def test_blocks_md_edit_with_internal_reference(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/README.md",
            "old_string": "old text",
            "new_string": "Check rules/code-style.md for guidance.",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


def test_blocks_md_multiedit_with_internal_reference(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/docs/x.md",
            "edits": [
                {"old_string": "a", "new_string": "see checklist.md for review"},
                {"old_string": "b", "new_string": "fine"},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


@pytest.mark.parametrize(
    "verb",
    ["commit -F -", "tag -a v1.2.0 -F -", "notes add -F -"],
)
def test_allows_chore_commit_type_in_git_messages(tool_use, run_hook, verb):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"git {verb} <<'MSG'\nchore: ignore daemon runtime state\nMSG"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_chore_label_in_gh_comment(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": "gh pr comment 1 --body \"$(cat <<'BODY'\nchore: rename the helper\nBODY\n)\""
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


def test_blocks_review_label_in_git_commit_message(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "git commit -F -\nnitpick: rename the helper\nMSG"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


def test_allows_clean_gh_comment(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'Fixed the null pointer in user service'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_clean_md_write(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/README.md",
            "content": "# Project\n\nThis project does X.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
