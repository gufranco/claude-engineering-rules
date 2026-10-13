from __future__ import annotations

import os

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.staged_blobs import (  # noqa: E402
    CommitRequest,
    StagedDocument,
    StagedScanError,
    commit_request,
    staged_documents,
)
from git_repo_fixture import GitRepo, isolated_git_env, new_git_repo  # noqa: E402


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> GitRepo:
    for key, value in isolated_git_env().items():
        monkeypatch.setenv(key, value)
    return new_git_repo(tmp_path)


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git commit -m x", CommitRequest("/w", False)),
        ("git -C sub commit -m x", CommitRequest("/w/sub", False)),
        ("git -C /abs -c a=b commit -qm x", CommitRequest("/abs", False)),
        ("cd /abs && git commit -am x", CommitRequest("/abs", True)),
        ("cd 'a b'; git commit --all", CommitRequest("/w/a b", True)),
        ("FOO=1 git commit --amend --no-edit", CommitRequest("/w", False)),
        ("make lint && git commit -m 'x -a'", CommitRequest("/w", False)),
        ("git add . && git commit -m x", CommitRequest("/w", False)),
    ],
)
def test_recognises_a_commit_call(command: str, expected: CommitRequest) -> None:
    # Arrange
    cwd = "/w"

    # Act
    request = commit_request(command, cwd)

    # Assert
    assert request == expected


@pytest.mark.parametrize(
    "command",
    ["git status", 'echo "git commit"', "git commit-tree abc", "grep 'git commit' log"],
)
def test_ignores_a_command_that_does_not_commit(command: str) -> None:
    # Arrange
    cwd = "/w"

    # Act
    request = commit_request(command, cwd)

    # Assert
    assert request is None


def test_reads_a_new_staged_file_against_an_empty_before(repo: GitRepo) -> None:
    # Arrange
    repo.stage("src/a.py", "x = 1\n")
    expected = StagedDocument("src/a.py", "", "x = 1\n")

    # Act
    documents = staged_documents(CommitRequest(str(repo.root), False))

    # Assert
    assert documents == [expected]


def test_reads_a_modified_file_against_head(repo: GitRepo) -> None:
    # Arrange
    repo.stage("a.py", "x = 1\n")
    repo.commit()
    repo.stage("a.py", "x = 2\n")
    repo.write("a.py", "x = 3\n")
    expected = StagedDocument("a.py", "x = 1\n", "x = 2\n")

    # Act
    documents = staged_documents(CommitRequest(str(repo.root), False))

    # Assert
    assert documents == [expected]


def test_reads_the_worktree_when_the_commit_stages_tracked_files(repo: GitRepo) -> None:
    # Arrange
    repo.stage("a.py", "x = 1\n")
    repo.commit()
    repo.write("a.py", "x = 3\n")
    expected = StagedDocument("a.py", "x = 1\n", "x = 3\n")

    # Act
    documents = staged_documents(CommitRequest(str(repo.root), True))

    # Assert
    assert documents == [expected]


def test_reads_a_renamed_file_against_its_old_path(repo: GitRepo) -> None:
    # Arrange
    body = "".join(f"value_{index} = {index}\n" for index in range(20))
    repo.stage("old.py", body)
    repo.commit()
    repo.git("mv", "old.py", "new.py")
    expected = StagedDocument("new.py", body, body)

    # Act
    documents = staged_documents(CommitRequest(str(repo.root), False))

    # Assert
    assert documents == [expected]


def test_skips_a_deleted_or_binary_file(repo: GitRepo) -> None:
    # Arrange
    repo.stage("gone.py", "x = 1\n")
    repo.commit()
    repo.git("rm", "-q", "gone.py")
    (repo.root / "blob.bin").write_bytes(b"\xff\xfe\x00\x01")
    repo.git("add", "blob.bin")

    # Act
    documents = staged_documents(CommitRequest(str(repo.root), False))

    # Assert
    assert documents == []


def test_returns_nothing_outside_a_repository(tmp_path: Path) -> None:
    # Arrange
    request = CommitRequest(str(tmp_path), False)

    # Act
    documents = staged_documents(request)

    # Assert
    assert documents == []


def test_fails_closed_when_git_cannot_read_the_index(
    repo: GitRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    broken_index = repo.root / "broken-index"
    broken_index.write_bytes(b"not an index")
    monkeypatch.setenv("GIT_INDEX_FILE", str(broken_index))

    # Act
    with pytest.raises(StagedScanError) as raised:
        staged_documents(CommitRequest(str(repo.root), False))

    # Assert
    assert "diff" in str(raised.value)


def test_keeps_an_unparseable_directory_word_verbatim() -> None:
    # Arrange
    command = "cd $(echo \") && git commit -m 'open"

    # Act
    request = commit_request(command, "/w")

    # Assert
    assert request == CommitRequest('/w/$(echo ")', False)


def test_returns_nothing_for_a_missing_directory(tmp_path: Path) -> None:
    # Arrange
    request = CommitRequest(str(tmp_path / "absent"), False)

    # Act
    documents = staged_documents(request)

    # Assert
    assert documents == []


def test_skips_a_staged_file_past_the_size_ceiling(repo: GitRepo) -> None:
    # Arrange
    repo.stage("big.py", "x = 1\n" * 100_000)

    # Act
    documents = staged_documents(CommitRequest(str(repo.root), False))

    # Assert
    assert documents == []


@pytest.mark.skipif(
    os.geteuid() == 0, reason="root reads files without permission bits"
)
def test_skips_an_unreadable_worktree_file(repo: GitRepo) -> None:
    # Arrange
    repo.stage("a.py", "x = 1\n")
    repo.commit()
    target = repo.write("a.py", "x = 2\n")
    target.chmod(0)

    # Act
    documents = staged_documents(CommitRequest(str(repo.root), True))

    # Assert
    assert documents == []
