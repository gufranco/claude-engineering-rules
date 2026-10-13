from __future__ import annotations

import pytest
from _ppw_support import (
    GIT_ENV,
    HOOK,
    bash,
    make_repo,
    repo_with_tracked_prompt,
    repo_with_untracked_prompt,
    run_git,
    write,
)


@pytest.mark.parametrize(
    "command",
    [
        "git add notes/PROMPT.md",
        "git add -f notes/PROMPT.md",
        "git add .",
        "git add -A",
        "git add --all",
        "git -C notes add .",
        "git stage notes",
        "git add 'notes/*.md'",
        "npm test && git add . && git commit -m wip",
        "command git add -f notes/PROMPT.md",
        "(git add -f notes/PROMPT.md)",
        "cd notes && git add -f PROMPT.md",
    ],
)
def test_prompt_blocks_an_add_that_would_stage_it(
    run_hook, tool_use, tmp_path, command
):
    # Arrange
    repo = repo_with_untracked_prompt(tmp_path)

    # Act
    code, _, stderr = bash(run_hook, tool_use, repo, command)

    # Assert
    assert code == 2
    assert "PROMPT.md" in stderr


def test_prompt_match_ignores_case(run_hook, tool_use, tmp_path):
    # Arrange
    repo = repo_with_untracked_prompt(tmp_path, "notes/prompt.md")

    # Act
    code, _, _ = bash(run_hook, tool_use, repo, "git add notes/prompt.md")

    # Assert
    assert code == 2


@pytest.mark.parametrize(
    "command",
    [
        "git add src/main.py",
        "git add -u",
        "git add",
        "git commit -m 'unrelated change'",
    ],
)
def test_prompt_allows_adds_and_commits_that_leave_it_out(
    run_hook, tool_use, tmp_path, command
):
    # Arrange
    repo = repo_with_untracked_prompt(tmp_path)
    write(repo, "src/main.py")

    # Act
    code, _, _ = bash(run_hook, tool_use, repo, command)

    # Assert
    assert code == 0


def test_prompt_blocks_a_commit_with_it_staged(run_hook, tool_use, tmp_path):
    # Arrange
    repo = repo_with_untracked_prompt(tmp_path)
    run_git(repo, "add", "-f", "notes/PROMPT.md")

    # Act
    code, _, stderr = bash(run_hook, tool_use, repo, "git commit -m wip")

    # Assert
    assert code == 2
    assert "notes/PROMPT.md" in stderr


@pytest.mark.parametrize(
    "command",
    [
        "git commit -am wip",
        "git commit -a -m wip",
        "git commit --all -m wip",
        "git commit -m wip -- planning/PROMPT.md",
        "git commit planning -m wip",
        "git commit --only -m wip planning",
    ],
)
def test_prompt_blocks_a_commit_that_records_a_tracked_edit(
    run_hook, tool_use, tmp_path, command
):
    # Arrange
    repo = repo_with_tracked_prompt(tmp_path)

    # Act
    code, _, _ = bash(run_hook, tool_use, repo, command)

    # Assert
    assert code == 2


def test_prompt_allows_a_commit_leaving_a_tracked_edit_unstaged(
    run_hook, tool_use, tmp_path
):
    # Arrange
    repo = repo_with_tracked_prompt(tmp_path)

    # Act
    code, _, _ = bash(
        run_hook, tool_use, repo, "git commit --author 'A <a@b.c>' -m wip"
    )

    # Assert
    assert code == 0


def test_prompt_allows_removing_it_from_the_index(run_hook, tool_use, tmp_path):
    # Arrange
    repo = repo_with_tracked_prompt(tmp_path)
    run_git(repo, "rm", "-q", "--cached", "planning/PROMPT.md")

    # Act
    code, _, _ = bash(run_hook, tool_use, repo, "git commit -m 'stop tracking'")

    # Assert
    assert code == 0


def test_prompt_allows_committing_a_deleted_tracked_prompt(
    run_hook, tool_use, tmp_path
):
    # Arrange
    repo = repo_with_tracked_prompt(tmp_path)
    (repo / "planning" / "PROMPT.md").unlink()

    # Act
    code, _, _ = bash(run_hook, tool_use, repo, "git commit -am 'drop prompt'")

    # Assert
    assert code == 0


def test_prompt_blocks_a_commit_when_git_fails(run_hook, tool_use, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")

    # Act
    code, _, stderr = bash(
        run_hook, tool_use, repo, "git commit -m wip", env={"PATH": str(tmp_path)}
    )

    # Assert
    assert code == 2
    assert "could not" in stderr


def test_prompt_blocks_an_unparseable_command_naming_it(run_hook, tool_use, tmp_path):
    # Arrange
    repo = repo_with_untracked_prompt(tmp_path)

    # Act
    code, _, _ = bash(run_hook, tool_use, repo, "git add 'notes/PROMPT.md")

    # Assert
    assert code == 2


def test_prompt_allows_git_commands_outside_a_repository(run_hook, tool_use, tmp_path):
    # Arrange
    write(tmp_path, "PROMPT.md")

    # Act
    code, _, _ = bash(run_hook, tool_use, tmp_path, "git add PROMPT.md")

    # Assert
    assert code == 0


def test_non_bash_tool_is_ignored(run_hook, tool_use, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    payload = tool_use(
        "Write", {"file_path": str(repo / "docs" / "x.md")}, cwd=str(repo)
    )

    # Act
    code, stdout, _ = run_hook(HOOK, payload, env=GIT_ENV)

    # Assert
    assert (code, stdout) == (0, "")


def test_prompt_ignores_an_add_named_inside_script_text(run_hook, tool_use, tmp_path):
    # Arrange
    repo = repo_with_untracked_prompt(tmp_path)
    command = "python3 - <<'EOF'\nprint('git add -f notes/PROMPT.md')\nEOF"

    # Act
    code, _, _ = bash(run_hook, tool_use, repo, command)

    # Assert
    assert code == 0
