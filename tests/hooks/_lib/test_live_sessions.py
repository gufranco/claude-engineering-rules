from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.live_sessions import (  # noqa: E402
    LiveSession,
    owner_of,
    sessions,
    sessions_dir,
)

fake = Faker()
Faker.seed(9188)
DEAD_PID = 2**22 + 17


def _write(folder: Path, pid: int, session: str, cwd: str, **extra: object) -> None:
    record = {"pid": pid, "sessionId": session, "cwd": cwd, "name": "dotfiles-3c"}
    (folder / f"{pid}.json").write_text(json.dumps({**record, **extra}), "utf-8")


def test_a_session_whose_process_is_alive_is_listed(tmp_path):
    # Arrange
    session = fake.uuid4()
    _write(tmp_path, os.getpid(), session, "/Users/x/.dotfiles", status="busy")

    # Act
    result = sessions(tmp_path)

    # Assert
    assert result == (
        LiveSession(session, "/Users/x/.dotfiles", "dotfiles-3c", "busy"),
    )


@pytest.mark.parametrize(
    "content",
    ["{broken", "[]", json.dumps({"pid": "x", "sessionId": "s", "cwd": "/a"})],
)
def test_unreadable_or_malformed_records_are_skipped(tmp_path, content):
    # Arrange
    (tmp_path / "1.json").write_text(content, "utf-8")

    # Act
    result = sessions(tmp_path)

    # Assert
    assert result == ()


def test_a_record_whose_process_exited_is_skipped(tmp_path):
    # Arrange
    _write(tmp_path, DEAD_PID, fake.uuid4(), "/Users/x/.dotfiles")

    # Act
    result = sessions(tmp_path)

    # Assert
    assert result == ()


def test_a_missing_sessions_folder_lists_nothing(tmp_path):
    # Arrange
    folder = tmp_path / "absent"

    # Act
    result = sessions(folder)

    # Assert
    assert result == ()


def _live(cwd: str, session: str | None = None) -> LiveSession:
    return LiveSession(session or fake.uuid4(), cwd, "other", "busy")


def test_a_write_inside_another_session_tree_names_that_session():
    # Arrange
    other = _live("/Users/x/.dotfiles")

    # Act
    result = owner_of(
        "/Users/x/.dotfiles/.releaserc.json", "/Users/x/.claude", "me", (other,)
    )

    # Assert
    assert result == other


@pytest.mark.parametrize(
    ("target", "own_cwd"),
    [
        ("/Users/x/.claude/README.md", "/Users/x/.claude"),
        ("/Users/x/Work/repo/a.py", "/Users/x/Work/repo"),
        ("/Users/x/.dotfiles-old/a", "/Users/x/.claude"),
    ],
)
def test_own_tree_ancestor_sessions_and_sibling_prefixes_are_not_foreign(
    target, own_cwd
):
    # Arrange
    others = (_live("/Users/x/Work"), _live("/Users/x/.dotfiles"))

    # Act
    result = owner_of(target, own_cwd, "me", others)

    # Assert
    assert result is None


def test_this_session_and_a_second_session_in_the_same_tree():
    # Arrange
    mine = _live("/Users/x/.dotfiles", "me")
    twin = _live("/Users/x/.dotfiles")

    # Act
    result = owner_of("/Users/x/.dotfiles/a", "/Users/x/.dotfiles", "me", (mine, twin))

    # Assert
    assert result == twin


def test_the_deepest_matching_session_owns_the_path():
    # Arrange
    outer = _live("/Users/x/Workspace")
    inner = _live("/Users/x/Workspace/kiyome")

    # Act
    result = owner_of(
        "/Users/x/Workspace/kiyome/test/io.bats",
        "/Users/x/.claude",
        "me",
        (outer, inner),
    )

    # Assert
    assert result == inner


def test_a_process_this_user_cannot_signal_still_counts_as_alive(tmp_path):
    # Arrange
    session = fake.uuid4()
    _write(tmp_path, 1, session, "/")

    # Act
    result = sessions(tmp_path)

    # Assert
    assert [live.session_id for live in result] == [session]


def test_the_sessions_folder_follows_the_environment_variable(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setenv("CLAUDE_SESSIONS_DIR", str(tmp_path / "s"))

    # Act
    result = sessions_dir()

    # Assert
    assert result == tmp_path / "s"


def test_the_sessions_folder_defaults_under_home(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.delenv("CLAUDE_SESSIONS_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    # Act
    result = sessions_dir()

    # Assert
    assert result == tmp_path / ".claude" / "sessions"
