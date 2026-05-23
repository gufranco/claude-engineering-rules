"""Coverage for internal-config-leakage hook.

Source rule: standards/code-review.md No Internal Config Leakage.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = "internal-config-leakage"


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
def test_blocks_tilde_claude_in_gh_commands(tool_use, assert_blocks, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act / Assert
    assert_blocks(HOOK, payload, "internal Claude config")


@pytest.mark.parametrize(
    "command",
    [
        "glab mr create --description 'See .claude/rules/x.md'",
        "glab issue create --description 'Look at .claude/rules/x.md'",
        "glab api projects/1/issues --field description='see .claude/skills/x.md'",
        "glab release create v1 --notes '.claude/standards/x.md'",
    ],
)
def test_blocks_dot_claude_dir_in_glab(tool_use, assert_blocks, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act / Assert
    assert_blocks(HOOK, payload, "internal Claude config")


def test_blocks_git_commit_message_with_internal_path(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "git commit -m 'fix per .claude/checklists/checklist.md cat 3'"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "internal Claude config")


def test_blocks_git_tag_with_internal_path(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "git tag -a v1 -m 'Per rules/security.md no-secret policy'"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "internal Claude config")


def test_blocks_git_notes_with_internal_reference(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "git notes add -m 'See rules/index.yml entry'"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "internal Claude config")


def test_blocks_slack_send_with_category_reference(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "slack send 'review failed at category 5'"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "internal Claude config")


def test_blocks_slack_cli_post(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "slack-cli post '#chan' 'see categories 12'"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "internal Claude config")


def test_blocks_curl_to_slack(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "internal Claude config")


def test_blocks_category_number_reference(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'Failed on category #3 checks'"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "category number")


def test_blocks_cat_shorthand(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'See cat 12 of the review checklist'"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "cat <n> shorthand")


def test_blocks_checklist_item_mention(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'Per checklist item 5 this fails'"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "checklist")


def test_blocks_md_write_with_internal_path(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/docs/notes.md",
            "content": "Refer to $HOME/.claude/rules/security.md for details.\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "internal Claude config")


def test_blocks_md_edit_with_internal_reference(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/README.md",
            "old_string": "old text",
            "new_string": "Check rules/code-style.md for guidance.",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "internal Claude config")


def test_blocks_md_multiedit_with_internal_reference(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "internal Claude config")


def test_allows_clean_gh_comment(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'Fixed the null pointer in user service'"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_clean_md_write(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/README.md",
            "content": "# Project\n\nThis project does X.\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_non_md_write_even_with_internal_reference(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// see $HOME/.claude/rules/code-style.md\nconst x = 1;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_non_publishing_bash(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "cat $HOME/.claude/rules/code-style.md"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_skipped_claude_md_path(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/gufranco/.claude/CLAUDE.md",
            "content": "See rules/index.yml and checklist.md for context.\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_skipped_rules_md_path(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/Users/gufranco/.claude/rules/example.md",
            "old_string": "old",
            "new_string": "Reference checklist.md cat 3 here.",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_skipped_hooks_path(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/gufranco/.claude/hooks/notes.md",
            "content": "Per category 12 of the checklist.md, this fires.\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_settings_json_edit(tool_use, assert_allows):
    # settings.json is the config itself and must reference ~/.claude paths
    payload = tool_use(
        "Edit",
        {
            "file_path": "/Users/gufranco/.claude/settings.json",
            "old_string": '"command": "python3 ~/.claude/hooks/foo.py"',
            "new_string": '"command": "python3 ~/.claude/hooks/bar.py"',
        },
    )
    assert_allows(HOOK, payload)


def test_allows_settings_local_json_edit(tool_use, assert_allows):
    payload = tool_use(
        "Edit",
        {
            "file_path": "/Users/gufranco/.claude/.claude/settings.local.json",
            "old_string": '"~/.claude/hooks/x.py"',
            "new_string": '"~/.claude/hooks/y.py"',
        },
    )
    assert_allows(HOOK, payload)


def test_allows_agents_path(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/gufranco/.claude/agents/example.md",
            "content": "Follow rules/code-style.md for context.\n",
        },
    )
    assert_allows(HOOK, payload)


def test_allows_tests_path(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/gufranco/.claude/tests/hooks/foo/test_foo.py",
            "content": "# Mentions ~/.claude/hooks/foo.py in assertion text.\n",
        },
    )
    assert_allows(HOOK, payload)


def test_allows_projects_memory_path(tool_use, assert_allows):
    # Memory files legitimately reference repo paths to teach the model
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/gufranco/.claude/projects/-Users-gufranco--claude/memory/feedback_x.md",
            "content": "See ~/.claude/rules/x.md for the rule.\n",
        },
    )
    assert_allows(HOOK, payload)


def test_disable_env_bypasses(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'See .claude/rules/x.md'"},
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"CONFIG_LEAKAGE_DISABLE": "1"})


def test_disable_env_other_value_does_not_bypass(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'See .claude/rules/x.md'"},
    )

    # Act / Assert
    assert_blocks(
        HOOK,
        payload,
        "internal Claude config",
        env={"CONFIG_LEAKAGE_DISABLE": "0"},
    )


def test_unknown_tool_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/notes.md"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_write_non_string_content_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/docs/x.md", "content": 42},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_bash_non_string_command_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": 12345})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_non_dict_edits_are_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/docs/x.md",
            "edits": ["not a dict", None, 42],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_non_string_new_string(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/docs/x.md",
            "edits": [{"old_string": "a", "new_string": 999}],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_edit_with_non_string_new_string(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/docs/x.md",
            "old_string": "a",
            "new_string": 999,
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_empty_file_path_md_write_is_treated_as_non_md(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "Reference rules/index.yml here.\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_md_write_without_findings_passes(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/CHANGELOG.md",
            "content": "## v1\n- added a new feature\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "internal-config-leakage.py"
    )
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    for k in ("COVERAGE_PROCESS_START", "PYTHONPATH"):
        if k in os.environ:
            env[k] = os.environ[k]

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
