from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.tracked_files import removes_only_uncommitted_tests  # noqa: E402

fake = Faker()
Faker.seed(6031)


def _repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    for args in (
        ["init", "-q"],
        ["config", "user.email", f"{fake.user_name()}@repo.test"],
        ["config", "user.name", fake.name()],
        ["config", "commit.gpgsign", "false"],
    ):
        subprocess.run(["git", "-C", str(repo), *args], check=True, timeout=30)
    return repo


def _commit(repo: Path, name: str) -> None:
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", name], check=True, timeout=30)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "add"], check=True, timeout=30
    )


def test_an_untracked_spec_the_session_created_is_exempt(tmp_path):
    # Arrange
    repo = _repo(tmp_path)
    (repo / "shots.spec.ts").write_text("test()\n", encoding="utf-8")

    # Act
    result = removes_only_uncommitted_tests("rm -f shots.spec.ts", str(repo))

    # Assert
    assert result is True


def test_a_tracked_test_is_not_exempt(tmp_path):
    # Arrange
    repo = _repo(tmp_path)
    _commit(repo, "orders.test.ts")

    # Act
    result = removes_only_uncommitted_tests("rm orders.test.ts", str(repo))

    # Assert
    assert result is False


def test_a_test_removed_from_the_index_but_still_in_history_is_not_exempt(tmp_path):
    # Arrange
    repo = _repo(tmp_path)
    _commit(repo, "tests/test_orders.py")
    subprocess.run(
        ["git", "-C", str(repo), "rm", "-q", "--cached", "tests/test_orders.py"],
        check=True,
        timeout=30,
    )

    # Act
    result = removes_only_uncommitted_tests("rm tests/test_orders.py", str(repo))

    # Assert
    assert result is False


@pytest.mark.parametrize(
    "command",
    ["rm missing.test.ts", "git rm stale.test.ts", "rm notes.txt"],
)
def test_a_missing_file_git_rm_or_no_test_target_is_not_exempt(tmp_path, command):
    # Arrange
    repo = _repo(tmp_path)
    (repo / "stale.test.ts").write_text("x\n", encoding="utf-8")
    (repo / "notes.txt").write_text("x\n", encoding="utf-8")

    # Act
    result = removes_only_uncommitted_tests(command, str(repo))

    # Assert
    assert result is False


def test_a_file_outside_any_repository_counts_as_uncommitted(tmp_path):
    # Arrange
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "capture.spec.ts").write_text("test()\n", encoding="utf-8")

    # Act
    result = removes_only_uncommitted_tests("rm capture.spec.ts", str(scratch))

    # Assert
    assert result is True


def test_an_unavailable_git_keeps_the_confirmation(tmp_path, monkeypatch):
    # Arrange
    (tmp_path / "x.spec.ts").write_text("x\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "no-git-here"))

    # Act
    result = removes_only_uncommitted_tests("rm x.spec.ts", str(tmp_path))

    # Assert
    assert result is False
