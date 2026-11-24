from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "dirty-tree-push-guard"
GIT_TIMEOUT_S = 30.0


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, timeout=GIT_TIMEOUT_S)


@pytest.fixture
def committed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "app.ts").write_text("export const a = 1;\n", encoding="utf-8")
    (repo / "app.test.ts").write_text("test('a', () => {});\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


@pytest.fixture
def dirty_repo(committed_repo: Path) -> Path:
    (committed_repo / "app.test.ts").write_text(
        "test('b', () => {});\n", encoding="utf-8"
    )
    return committed_repo


@pytest.mark.parametrize(
    "cmd",
    [
        "git push origin main",
        "git push",
        "git add app.ts && git commit -m fix && git push origin main",
        "git commit -q -F - && git push origin main 2>&1 | tail -1",
    ],
)
def test_blocks_push_while_tracked_files_are_modified(
    tool_use, run_hook, dirty_repo, cmd
):
    # Arrange
    payload = tool_use("Bash", {"command": cmd}, cwd=str(dirty_repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "app.test.ts")


def test_blocks_push_into_a_repository_named_by_cd(
    tool_use, run_hook, dirty_repo, tmp_path
):
    # Arrange
    cmd = f"cd {dirty_repo} && git push origin main"
    payload = tool_use("Bash", {"command": cmd}, cwd=str(tmp_path))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "not the tree that was tested")


def test_blocks_push_into_a_repository_named_by_dash_c(
    tool_use, run_hook, dirty_repo, tmp_path
):
    # Arrange
    cmd = f'git -C "{dirty_repo}" push origin main'
    payload = tool_use("Bash", {"command": cmd}, cwd=str(tmp_path))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "app.test.ts")


@pytest.mark.parametrize(
    "cmd",
    [
        "git add -A && git commit -m fix && git push origin main",
        "git add --all && git commit -m fix && git push",
        "git add . && git commit -m fix && git push",
        "git commit -am fix && git push",
        "git commit -a -m fix && git push",
        "git commit --all -m fix && git push",
        "git status --short",
        "git diff --stat",
    ],
)
def test_allows_pushes_that_stage_everything_and_commands_that_do_not_push(
    tool_use, run_hook, dirty_repo, cmd
):
    # Arrange
    payload = tool_use("Bash", {"command": cmd}, cwd=str(dirty_repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_push_from_a_clean_tree(tool_use, run_hook, committed_repo):
    # Arrange
    payload = tool_use(
        "Bash", {"command": "git push origin main"}, cwd=str(committed_repo)
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_push_with_only_untracked_files(tool_use, run_hook, committed_repo):
    # Arrange
    (committed_repo / "notes.txt").write_text("scratch\n", encoding="utf-8")
    payload = tool_use("Bash", {"command": "git push"}, cwd=str(committed_repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_push_outside_a_repository(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use("Bash", {"command": "git push"}, cwd=str(tmp_path))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_disable_env_allows_a_dirty_push(tool_use, run_hook, dirty_repo):
    # Arrange
    payload = tool_use("Bash", {"command": "git push"}, cwd=str(dirty_repo))

    # Act
    result = run_hook(HOOK, payload, env={"DIRTY_TREE_PUSH_GUARD_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_ignores_other_tools_and_empty_commands(tool_use, run_hook, dirty_repo):
    # Arrange
    payloads = [
        tool_use("Read", {"file_path": "app.ts"}, cwd=str(dirty_repo)),
        tool_use("Bash", {"command": ""}, cwd=str(dirty_repo)),
    ]

    # Act
    results = [run_hook(HOOK, payload) for payload in payloads]

    # Assert
    for result in results:
        assert_allowed(result)


def test_allows_push_when_git_cannot_run(tool_use, run_hook, dirty_repo):
    # Arrange
    payload = tool_use("Bash", {"command": "git push"}, cwd=str(dirty_repo))

    # Act
    result = run_hook(HOOK, payload, env={"PATH": ""})

    # Assert
    assert_allowed(result)
