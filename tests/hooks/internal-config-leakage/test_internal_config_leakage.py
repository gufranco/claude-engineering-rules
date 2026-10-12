from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

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
            "file_path": "/Users/gufranco/.claude/CLAUDE.md",
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
            "file_path": "/Users/gufranco/.claude/rules/example.md",
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
            "file_path": "/Users/gufranco/.claude/hooks/notes.md",
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
            "file_path": "/Users/gufranco/.claude/settings.json",
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
            "file_path": "/Users/gufranco/.claude/.claude/settings.local.json",
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
            "file_path": "/Users/gufranco/.claude/agents/example.md",
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
            "file_path": "/Users/gufranco/.claude/tests/hooks/foo/test_foo.py",
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
            "file_path": "/Users/gufranco/.claude/projects/-Users-gufranco--claude/memory/feedback_x.md",
            "content": "See ~/.claude/rules/x.md for the rule.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_disable_env_bypasses(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'See .claude/rules/x.md'"},
    )

    # Act
    result = run_hook(HOOK, payload, env={"CONFIG_LEAKAGE_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_disable_env_other_value_does_not_bypass(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 1 --body 'See .claude/rules/x.md'"},
    )

    # Act
    result = run_hook(HOOK, payload, env={"CONFIG_LEAKAGE_DISABLE": "0"})

    # Assert
    assert_blocked(result, "internal Claude config")


def test_unknown_tool_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/notes.md"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_non_string_content_is_safe(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/docs/x.md", "content": 42},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_bash_non_string_command_is_safe(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": 12345})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_multiedit_non_dict_edits_are_safe(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/docs/x.md",
            "edits": ["not a dict", None, 42],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_multiedit_non_string_new_string(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/docs/x.md",
            "edits": [{"old_string": "a", "new_string": 999}],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_edit_with_non_string_new_string(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/docs/x.md",
            "old_string": "a",
            "new_string": 999,
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_empty_file_path_md_write_is_treated_as_non_md(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "Reference rules/index.yml here.\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_md_write_without_findings_passes(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/CHANGELOG.md",
            "content": "## v1\n- added a new feature\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "internal-config-leakage.py"
    )
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


def test_allows_config_paths_inside_the_second_brain_vault(
    tool_use, run_hook, tmp_path
):
    # Arrange
    vault = tmp_path / "vault" / "wiki" / "concepts"
    vault.mkdir(parents=True)
    target = vault / "Tooling.md"
    payload = tool_use(
        "Write",
        {
            "file_path": str(target),
            "content": "MCP servers load from ~/.claude.json, not ~/.claude/settings.json.\n",
        },
    )

    # Act
    result = run_hook(
        HOOK, payload, env={"SECOND_BRAIN_VAULT": str(tmp_path / "vault")}
    )

    # Assert
    assert_allowed(result)


def test_still_blocks_config_paths_outside_the_vault(tool_use, run_hook, tmp_path):
    # Arrange
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "project" / "NOTES.md"
    outside.parent.mkdir()
    payload = tool_use(
        "Write",
        {
            "file_path": str(outside),
            "content": "MCP servers load from ~/.claude.json, not ~/.claude/settings.json.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"SECOND_BRAIN_VAULT": str(vault)})

    # Assert
    assert_blocked(result)


GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
CONFIG_TEXT = "Read `CLAUDE.md` and ~/.claude/settings.json before continuing.\n"


def make_repo(root: Path) -> Path:
    subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=root,
        check=True,
        capture_output=True,
        env={**os.environ, **GIT_ENV},
    )
    return root


def test_allows_config_paths_in_the_local_workspace(tool_use, run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path)
    target = repo / "docs" / "PROMPT.md"
    payload = tool_use("Write", {"file_path": str(target), "content": CONFIG_TEXT})

    # Act
    result = run_hook(HOOK, payload, env=GIT_ENV)

    # Assert
    assert_allowed(result)


def test_still_blocks_config_paths_in_project_owned_docs(tool_use, run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "index.md").write_text("# Project docs\n")
    target = repo / "docs" / "guide.md"
    payload = tool_use("Write", {"file_path": str(target), "content": CONFIG_TEXT})

    # Act
    result = run_hook(HOOK, payload, env=GIT_ENV)

    # Assert
    assert_blocked(result)
