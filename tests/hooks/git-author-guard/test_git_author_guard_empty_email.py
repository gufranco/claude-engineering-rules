from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_blocked

HOOK = "git-author-guard"
REAL_EMAIL = "dev@corp.test"


def git(repo: Path, env: dict[str, str], *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        env={**os.environ, **env},
        check=True,
        capture_output=True,
    )


def repo_with_identity(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    config = tmp_path / "gitconfig"
    config.write_text(
        f"[user]\n\tname = Dev\n\temail = {REAL_EMAIL}\n[commit]\n\tgpgsign = false\n",
        encoding="utf-8",
    )
    env = {"GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_NOSYSTEM": "1"}
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, env, "init", "-q", "-b", "trunk")
    return repo, env


def without_upstream(tmp_path: Path, repo: Path, env: dict[str, str]) -> None:
    return None


def with_upstream(tmp_path: Path, repo: Path, env: dict[str, str]) -> None:
    remote = tmp_path / "remote.git"
    git(tmp_path, env, "init", "-q", "--bare", str(remote))
    git(repo, env, "remote", "add", "origin", str(remote))
    git(repo, env, "commit", "-q", "--allow-empty", "-m", "chore: base")
    git(repo, env, "push", "-q", "-u", "origin", "trunk")


def commit_with_empty_author_email(repo: Path, env: dict[str, str]) -> None:
    git(repo, env, "commit", "-q", "--allow-empty", "--author=Dev <>", "-m", "chore: x")


@pytest.mark.parametrize("prepare_remote", [without_upstream, with_upstream])
def test_push_of_a_commit_with_an_empty_author_email_is_blocked(
    tmp_path, tool_use, run_hook, prepare_remote
):
    # Arrange
    repo, env = repo_with_identity(tmp_path)
    prepare_remote(tmp_path, repo, env)
    commit_with_empty_author_email(repo, env)
    payload = tool_use("Bash", {"command": f"git -C {repo} push origin trunk"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "empty author email")
