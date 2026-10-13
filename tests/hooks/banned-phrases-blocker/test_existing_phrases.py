from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
import os
import subprocess
import sys
from pathlib import Path

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
def test_publishing_bash_blocks_openers(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"gh pr comment 123 --body '{phrase} This is the fix.'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "banned phrase")


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
def test_publishing_bash_blocks_closers(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"git commit -m 'fix: address issue. {phrase}.'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "banned phrase")


@pytest.mark.parametrize(
    "phrase",
    [
        "It's worth noting",
        "It should be noted",
        "Keep in mind that",
    ],
)
def test_publishing_bash_blocks_hedges(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {
            "command": f"gh issue create --title 'X' --body '{phrase} the query is slow.'"
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "banned phrase")


@pytest.mark.parametrize(
    "phrase",
    [
        "That said,",
        "With that in mind,",
        "Having said that,",
        "On that note,",
    ],
)
def test_publishing_bash_blocks_transitions(tool_use, run_hook, phrase):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"gh pr create --title 'fix' --body '{phrase} we ship.'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "banned phrase")


@pytest.mark.parametrize(
    "fluff",
    ["robust", "comprehensive", "seamless", "elegant", "powerful"],
)
def test_markdown_write_blocks_fluff(tool_use, run_hook, fluff):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/README.md",
            "content": f"# Project\n\nA {fluff} solution for X.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "banned phrase")


def test_markdown_edit_blocks_opener(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/notes.md",
            "old_string": "Notes",
            "new_string": "Great question! Here are the notes.",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "banned phrase")


def test_markdown_multiedit_blocks_closer(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "banned phrase")


def test_write_to_md_without_file_path_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"content": "A robust comprehensive solution."},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skipped_md_paths_are_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/dev/.claude/CLAUDE.md",
            "content": "# Banned: robust, comprehensive, seamless.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skipped_rules_dir_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/Users/dev/.claude/rules/example.md",
            "old_string": "old",
            "new_string": "A list of robust patterns: comprehensive coverage.",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_changelog_md_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/CHANGELOG.md",
            "content": "## Added\n- A robust feature.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_non_md_write_is_allowed_even_with_fluff(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// A robust comprehensive seamless implementation.\nconst x = 1;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_clean_bash_command_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "git commit -m 'fix: handle null user id in service'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_non_publishing_bash_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "echo 'This is a robust comprehensive seamless message'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_disable_env_bypasses_all_phrases(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'Great question! Hope this helps.'"},
    )

    # Act
    result = run_hook(HOOK, payload, env={"BANNED_PHRASES_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_disable_env_value_other_than_one_does_not_bypass(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'Great question!'"},
    )

    # Act
    result = run_hook(HOOK, payload, env={"BANNED_PHRASES_DISABLE": "0"})

    # Assert
    assert_blocked(result, "banned phrase")


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "banned-phrases-blocker.py"
    )
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    env["CLAUDE_BYPASS_STATE"] = os.devnull

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
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr
