"""Regression coverage for banned-phrases-blocker's pre-existing branches.

Confirms the Agent/Task addition did not regress the original coverage of
publishing Bash commands and Markdown writes/edits.

Source rule: `~/.claude/CLAUDE.md` Banned Phrases.
"""

from __future__ import annotations

import pytest

HOOK = "banned-phrases-blocker"


@pytest.mark.parametrize(
    "phrase",
    [
        "Great question!",
        "Sure!",
        "Absolutely!",
        "Of course!",
        "Perfect!",
        "Excellent!",
        "Wonderful!",
    ],
)
def test_publishing_bash_blocks_openers(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"gh pr comment 123 --body '{phrase} This is the fix.'"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "banned phrase")


@pytest.mark.parametrize(
    "phrase",
    [
        "Let me know if you need anything else",
        "Hope this helps",
        "Hope that helps",
        "Feel free to ask",
        "Happy to help",
    ],
)
def test_publishing_bash_blocks_closers(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"git commit -m 'fix: address issue. {phrase}.'"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "banned phrase")


@pytest.mark.parametrize(
    "phrase",
    [
        "It's worth noting",
        "It should be noted",
        "Keep in mind that",
    ],
)
def test_publishing_bash_blocks_hedges(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": f"gh issue create --title 'X' --body '{phrase} the query is slow.'"
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "banned phrase")


@pytest.mark.parametrize(
    "phrase",
    [
        "That said,",
        "With that in mind,",
        "Having said that,",
        "On that note,",
    ],
)
def test_publishing_bash_blocks_transitions(tool_use, assert_blocks, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"gh pr create --title 'fix' --body '{phrase} we ship.'"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "banned phrase")


@pytest.mark.parametrize(
    "fluff",
    ["robust", "comprehensive", "seamless", "elegant", "powerful"],
)
def test_markdown_write_blocks_fluff(tool_use, assert_blocks, fluff):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/README.md",
            "content": f"# Project\n\nA {fluff} solution for X.\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "banned phrase")


def test_markdown_edit_blocks_opener(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/notes.md",
            "old_string": "Notes",
            "new_string": "Great question! Here are the notes.",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "banned phrase")


def test_markdown_multiedit_blocks_closer(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/notes.md",
            "edits": [
                {"old_string": "a", "new_string": "Hope this helps with section a."},
                {"old_string": "b", "new_string": "Section b stays clean."},
            ],
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "banned phrase")


def test_write_to_md_without_file_path_is_allowed(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"content": "A robust comprehensive solution."},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skipped_md_paths_are_allowed(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/gufranco/.claude/CLAUDE.md",
            "content": "# Banned: robust, comprehensive, seamless.\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skipped_rules_dir_is_allowed(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/Users/gufranco/.claude/rules/example.md",
            "old_string": "old",
            "new_string": "A list of robust patterns: comprehensive coverage.",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_changelog_md_is_allowed(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/CHANGELOG.md",
            "content": "## Added\n- A robust feature.\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_non_md_write_is_allowed_even_with_fluff(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// A robust comprehensive seamless implementation.\nconst x = 1;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_clean_bash_command_is_allowed(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "git commit -m 'fix: handle null user id in service'"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_non_publishing_bash_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "echo 'This is a robust comprehensive seamless message'"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_disable_env_bypasses_all_phrases(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'Great question! Hope this helps.'"},
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"BANNED_PHRASES_DISABLE": "1"})


def test_disable_env_value_other_than_one_does_not_bypass(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'Great question!'"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "banned phrase", env={"BANNED_PHRASES_DISABLE": "0"})


def test_invalid_json_stdin_does_not_crash(run_hook):
    # Arrange
    import os
    import subprocess
    import sys
    from pathlib import Path

    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "banned-phrases-blocker.py"
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not valid json",
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )

    # Assert
    assert proc.returncode == 0
