from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.pr_session_ledger import (  # noqa: E402
    create_repos,
    ledger_dir,
    opened,
    record,
)

fake = Faker()
Faker.seed(8821)
NOW = 1_800_000_000.0
WEEK = 7 * 24 * 3600


def _session() -> str:
    return fake.uuid4()


def _url(slug: str, number: int) -> str:
    return f"https://github.com/{slug}/pull/{number}\n"


def _repo(root: Path, remote: str) -> Path:
    repo = root / fake.word()
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=30)
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", remote],
        check=True,
        timeout=30,
    )
    return repo


def test_a_recorded_pr_is_reported_for_the_same_repository(tmp_path):
    # Arrange
    session = _session()
    record(session, _url("acme/app", 671), tmp_path, NOW)

    # Act
    result = opened(session, "Acme/App", tmp_path)

    # Assert
    assert result == ("acme/app#671",)


def test_another_repository_or_session_reports_nothing(tmp_path):
    # Arrange
    session = _session()
    record(session, _url("acme/app", 671), tmp_path, NOW)

    # Act
    result = (
        opened(session, "acme/api", tmp_path),
        opened(_session(), "acme/app", tmp_path),
    )

    # Assert
    assert result == ((), ())


def test_recording_twice_keeps_each_pr_once(tmp_path):
    # Arrange
    session = _session()
    record(session, _url("acme/app", 671), tmp_path, NOW)

    # Act
    record(session, _url("acme/app", 671) + _url("acme/app", 677), tmp_path, NOW)

    # Assert
    assert opened(session, "acme/app", tmp_path) == ("acme/app#671", "acme/app#677")


@pytest.mark.parametrize("session", ["", "../escape", "a b"])
def test_an_unsafe_session_id_or_text_without_a_url_writes_nothing(tmp_path, session):
    # Arrange
    directory = tmp_path / "ledger"

    # Act
    record(session, _url("acme/app", 1), directory, NOW)
    record(_session(), "no pull request here", directory, NOW)

    # Assert
    assert not directory.exists()


def test_ledgers_older_than_a_week_are_pruned_on_write(tmp_path):
    # Arrange
    stale = tmp_path / "old-session.json"
    stale.write_text(json.dumps(["acme/app#1"]), encoding="utf-8")
    os.utime(stale, (NOW - WEEK - 1, NOW - WEEK - 1))

    # Act
    record(_session(), _url("acme/app", 2), tmp_path, NOW)

    # Assert
    assert not stale.exists()


def test_a_corrupt_ledger_raises_instead_of_reading_as_empty(tmp_path):
    # Arrange
    session = _session()
    (tmp_path / f"{session}.json").write_text("{not json", encoding="utf-8")

    # Act
    attempt = lambda: opened(session, "acme/app", tmp_path)  # noqa: E731

    # Assert
    with pytest.raises(ValueError):
        attempt()


def test_create_repos_reads_the_repo_flag_or_the_origin_remote_after_a_cd(tmp_path):
    # Arrange
    repo = _repo(tmp_path, "git@github-work:acme/admin.git")
    command = (
        f"cd {repo} && gh pr create -t x -b y; "
        "GH_TOKEN=t gh pr create --repo acme/web -t x -b y; gh pr view 3"
    )

    # Act
    result = create_repos(command, str(tmp_path))

    # Assert
    assert result == ["acme/admin", "acme/web"]


def test_create_repos_takes_the_repo_equals_form(tmp_path):
    # Arrange
    command = "gh pr create -t x -b y --repo=acme/x"

    # Act
    result = create_repos(command, str(tmp_path))

    # Assert
    assert result == ["acme/x"]


def test_create_repos_skips_a_folder_with_no_remote(tmp_path):
    # Arrange
    folder = tmp_path / "plain"
    folder.mkdir()

    # Act
    result = create_repos("gh pr create -t x -b y", str(folder))

    # Assert
    assert result == []


def test_a_ledger_of_the_wrong_shape_raises(tmp_path):
    # Arrange
    session = _session()
    (tmp_path / f"{session}.json").write_text('{"acme/app": 1}', encoding="utf-8")

    # Act
    attempt = lambda: opened(session, "acme/app", tmp_path)  # noqa: E731

    # Assert
    with pytest.raises(ValueError, match="is not a list of pull requests"):
        attempt()


def test_a_ledger_written_this_week_survives_pruning(tmp_path):
    # Arrange
    recent = tmp_path / "recent-session.json"
    recent.write_text(json.dumps(["acme/app#1"]), encoding="utf-8")
    os.utime(recent, (NOW - 60, NOW - 60))

    # Act
    record(_session(), _url("acme/app", 2), tmp_path, NOW)

    # Assert
    assert recent.exists()


def test_an_unsafe_session_id_reads_nothing(tmp_path):
    # Arrange
    session = "../escape"

    # Act
    result = opened(session, "acme/app", tmp_path)

    # Assert
    assert result == ()


def test_the_ledger_folder_follows_the_environment_variable(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setenv("CLAUDE_PR_LEDGER_DIR", str(tmp_path / "ledger"))

    # Act
    result = ledger_dir()

    # Assert
    assert result == tmp_path / "ledger"


def test_the_ledger_folder_defaults_under_the_home_claude_folder(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.delenv("CLAUDE_PR_LEDGER_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    # Act
    result = ledger_dir()

    # Assert
    assert result == tmp_path / ".claude" / ".pr-session-ledger"
