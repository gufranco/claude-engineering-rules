from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _icl_support import (
    HOOK,
)


@pytest.mark.parametrize(
    "command",
    [
        "gh pr comment 1 --body 'See ~/.claude/CLAUDE.md for the rule'",
        "gh issue create --title 'x' --body 'Read ~/.claude/rules/x.md'",
        "gh api repos/o/r/issues --field body='~/.claude/'",
        "gh release create v1 --notes 'Updated ~/.claude config'",
        "gh gist create --desc 'snippet from ~/.claude'",
    ],
)
def test_blocks_tilde_claude_in_gh_commands(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


@pytest.mark.parametrize(
    "command",
    [
        "glab mr create --description 'See .claude/rules/x.md'",
        "glab issue create --description 'Look at .claude/rules/x.md'",
        "glab api projects/1/issues --field description='see .claude/skills/x.md'",
        "glab release create v1 --notes '.claude/standards/x.md'",
    ],
)
def test_blocks_dot_claude_dir_in_glab(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


def test_blocks_git_commit_message_with_internal_path(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "git commit -m 'fix per .claude/checklists/checklist.md cat 3'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


def test_blocks_git_tag_with_internal_path(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "git tag -a v1 -m 'Per rules/security.md no-secret policy'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


def test_blocks_git_notes_with_internal_reference(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "git notes add -m 'See rules/index.yml entry'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


@pytest.mark.parametrize(
    "command",
    [
        "git add rules/git-workflow.md && git commit -m 'docs: cover ignore hygiene'",
        "git add standards/code-review.md && git commit -am 'docs: tighten wording'",
        "git add checklists/checklist.md && git commit --message='docs: add a row'",
        "git add rules/security.md && git commit -F - <<'MSG'\ndocs: tighten wording\nMSG",
    ],
)
def test_allows_internal_paths_as_git_arguments(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "command",
    [
        "git add x.py && git commit -m 'docs: per rules/security.md'",
        "git add x.py && git commit -am 'docs: per rules/security.md'",
        "git add x.py && git commit --message='docs: per rules/security.md'",
        "git add x.py && git commit -F - <<'MSG'\ndocs: tighten\n\nSee rules/security.md\nMSG",
    ],
)
def test_still_blocks_internal_paths_inside_the_message(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


@pytest.mark.parametrize("flag", ["-F {}", "--file {}", "--file={}"])
def test_allows_internal_paths_as_arguments_beside_a_message_file(
    tool_use, run_hook, tmp_path, flag
):
    # Arrange
    message = tmp_path / "msg.txt"
    message.write_text("docs: tighten wording\n", encoding="utf-8")
    command = f"git add rules/security.md && git commit {flag.format(message)}"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_still_blocks_internal_paths_inside_a_message_file(
    tool_use, run_hook, tmp_path
):
    # Arrange
    message = tmp_path / "msg.txt"
    message.write_text("docs: tighten\n\nSee rules/security.md\n", encoding="utf-8")
    payload = tool_use("Bash", {"command": f"git add x.py && git commit -F {message}"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


def test_a_fixed_strings_flag_outside_a_commit_is_no_message_file(tool_use, run_hook):
    # Arrange
    command = "git log -F x && git commit --fixup rules/security.md"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


def test_blocks_whole_command_when_message_cannot_be_isolated(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git commit --fixup rules/security.md"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")


def test_blocks_gh_body_paired_with_a_clean_git_commit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": "git commit -m 'docs: tighten wording' && gh pr comment 1 --body 'see rules/security.md'"
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal Claude config")
