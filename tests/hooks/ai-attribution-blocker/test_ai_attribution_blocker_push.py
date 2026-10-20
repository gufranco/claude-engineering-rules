from __future__ import annotations

import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))

from git_repo_fixture import GitRepo, new_git_repo  # noqa: E402

HOOK = "ai-attribution-blocker"
FAKER_SEED = 20261020
SESSION_TRAILER = "Claude-Session: https://claude.ai/code/session_01AbCdEfGh"


@pytest.fixture
def faker() -> Faker:
    generator = Faker()
    generator.seed_instance(FAKER_SEED)
    return generator


def commit_with(repo: GitRepo, message: str) -> None:
    repo.git("commit", "-q", "--allow-empty", "-m", message)


def published_repo(tmp_path: Path, message: str) -> GitRepo:
    remote = tmp_path / "remote.git"
    repo = new_git_repo(tmp_path)
    repo.git("init", "-q", "--bare", str(remote))
    repo.git("remote", "add", "origin", str(remote))
    commit_with(repo, message)
    repo.git("push", "-q", "origin", "main")
    return repo


def test_blocks_a_push_whose_outgoing_commit_has_the_trailer(
    tool_use, run_hook, tmp_path, faker
):
    # Arrange
    repo = published_repo(tmp_path, faker.sentence())
    commit_with(repo, f"{faker.sentence()}\n\n{SESSION_TRAILER}")
    payload = tool_use("Bash", {"command": "git push"}, cwd=str(repo.root))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "outgoing commits")


def test_blocks_a_push_of_an_explicit_commit_with_the_trailer(
    tool_use, run_hook, tmp_path, faker
):
    # Arrange
    repo = published_repo(tmp_path, faker.sentence())
    commit_with(repo, f"{faker.sentence()}\n\n{SESSION_TRAILER}")
    tainted = repo.git("rev-parse", "HEAD").strip()
    repo.git("reset", "-q", "--hard", "HEAD~1")
    command = f"git -C {repo.root} push origin {tainted}:refs/heads/topic"
    payload = tool_use("Bash", {"command": command}, cwd=str(tmp_path))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "outgoing commits")


def test_allows_a_push_whose_outgoing_commits_are_clean(
    tool_use, run_hook, tmp_path, faker
):
    # Arrange
    repo = published_repo(tmp_path, faker.sentence())
    commit_with(repo, faker.sentence())
    payload = tool_use("Bash", {"command": "git push"}, cwd=str(repo.root))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_a_push_when_the_trailer_is_already_on_the_remote(
    tool_use, run_hook, tmp_path, faker
):
    # Arrange
    repo = published_repo(tmp_path, f"{faker.sentence()}\n\n{SESSION_TRAILER}")
    payload = tool_use("Bash", {"command": "git push"}, cwd=str(repo.root))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_a_push_whose_outgoing_commits_cannot_be_read(
    tool_use, run_hook, tmp_path
):
    # Arrange
    payload = tool_use("Bash", {"command": "git push"}, cwd=str(tmp_path))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "could not read outgoing commits")
