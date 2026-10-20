from __future__ import annotations

import sys
from pathlib import Path

import pytest
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.outgoing_commits import (  # noqa: E402
    PushInvocation,
    find_pushes,
    outgoing_messages,
)
from git_repo_fixture import GitRepo, new_git_repo  # noqa: E402

FAKER_SEED = 20261020


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


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git push", ("HEAD",)),
        ("git push origin", ("HEAD",)),
        ("git push -u origin feature", ("feature",)),
        ("git push origin 6b4c228:refs/heads/main", ("6b4c228",)),
        ("git push origin +topic:topic other", ("topic", "other")),
        ("git push origin :stale", ()),
        ("git push origin HEAD 2>&1", ("HEAD",)),
        ("git push origin feature > push.log", ("feature",)),
        ("git push origin feature >push.log 2>/dev/null", ("feature",)),
    ],
)
def test_find_pushes_reads_the_refspec_sources(command, expected):
    # Arrange
    cwd = "/work/repo"

    # Act
    pushes = find_pushes(command, cwd)

    # Assert
    assert pushes == (PushInvocation(cwd, expected),)


def test_find_pushes_follows_the_dash_c_directory():
    # Arrange
    command = "git -C /elsewhere push origin feature"

    # Act
    pushes = find_pushes(command, "/work/repo")

    # Assert
    assert pushes == (PushInvocation("/elsewhere", ("feature",)),)


def test_find_pushes_follows_a_leading_cd():
    # Arrange
    command = "cd /elsewhere && git push"

    # Act
    pushes = find_pushes(command, "/work/repo")

    # Assert
    assert pushes == (PushInvocation("/elsewhere", ("HEAD",)),)


def test_find_pushes_ignores_commands_that_do_not_push():
    # Arrange
    command = "git log --oneline && echo git push"

    # Act
    pushes = find_pushes(command, "/work/repo")

    # Assert
    assert pushes == ()


def test_outgoing_messages_returns_only_unpushed_commits(tmp_path, faker):
    # Arrange
    pushed = faker.sentence()
    unpushed = faker.sentence()
    repo = published_repo(tmp_path, pushed)
    commit_with(repo, unpushed)

    # Act
    messages = outgoing_messages(PushInvocation(str(repo.root), ("HEAD",)))

    # Assert
    assert messages == f"{unpushed}\n\n"


def test_outgoing_messages_is_empty_when_nothing_is_outgoing(tmp_path, faker):
    # Arrange
    repo = published_repo(tmp_path, faker.sentence())

    # Act
    messages = outgoing_messages(PushInvocation(str(repo.root), ("HEAD",)))

    # Assert
    assert messages == ""


def test_outgoing_messages_is_empty_for_a_delete_only_push(tmp_path):
    # Arrange
    push = PushInvocation(str(tmp_path), ())

    # Act
    messages = outgoing_messages(push)

    # Assert
    assert messages == ""


def test_outgoing_messages_is_none_outside_a_repository(tmp_path):
    # Arrange
    push = PushInvocation(str(tmp_path), ("HEAD",))

    # Act
    messages = outgoing_messages(push)

    # Assert
    assert messages is None


def test_outgoing_messages_is_none_for_an_unknown_source(tmp_path, faker):
    # Arrange
    repo = published_repo(tmp_path, faker.sentence())
    push = PushInvocation(str(repo.root), ("no-such-branch",))

    # Act
    messages = outgoing_messages(push)

    # Assert
    assert messages is None
