from __future__ import annotations

from _helpers.hook_assertions import assert_allowed
from _icl_support import (
    HOOK,
)


def test_allows_non_md_write_even_with_internal_reference(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// see $HOME/.claude/rules/code-style.md\nconst x = 1;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_non_publishing_bash(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "cat $HOME/.claude/rules/code-style.md"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_skipped_claude_md_path(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/dev/.claude/CLAUDE.md",
            "content": "See rules/index.yml and checklist.md for context.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_skipped_rules_md_path(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/Users/dev/.claude/rules/example.md",
            "old_string": "old",
            "new_string": "Reference checklist.md cat 3 here.",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_skipped_hooks_path(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/dev/.claude/hooks/notes.md",
            "content": "Per category 12 of the checklist.md, this fires.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_settings_json_edit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/Users/dev/.claude/settings.json",
            "old_string": '"command": "python3 ~/.claude/hooks/foo.py"',
            "new_string": '"command": "python3 ~/.claude/hooks/bar.py"',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_settings_local_json_edit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/Users/dev/.claude/.claude/settings.local.json",
            "old_string": '"~/.claude/hooks/x.py"',
            "new_string": '"~/.claude/hooks/y.py"',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_agents_path(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/dev/.claude/agents/example.md",
            "content": "Follow rules/code-style.md for context.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_tests_path(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/dev/.claude/tests/hooks/foo/test_foo.py",
            "content": "# Mentions ~/.claude/hooks/foo.py in assertion text.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_projects_memory_path(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/dev/.claude/projects/-Users-gufranco--claude/memory/feedback_x.md",
            "content": "See ~/.claude/rules/x.md for the rule.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
