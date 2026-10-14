from __future__ import annotations

import importlib
from collections.abc import Iterator
from pathlib import Path

import pytest

from _helpers.session_lock_support import (
    acquire,
    is_locked,
    module,
    release,
)


@pytest.fixture()
def custom_lock_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    target = tmp_path / "custom-locks.json"
    monkeypatch.setenv("CLAUDE_SESSION_LOCK_STATE", str(target))
    yield target
    monkeypatch.undo()
    importlib.reload(module)


def _boom(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("disk exploded")


def _unlink_boom(*_args: object, **_kwargs: object) -> None:
    raise OSError("cleanup denied")


class TestRelease:
    def test_removes_the_named_lock(self, state_path: Path) -> None:
        # Arrange
        acquire("morning", state_path=state_path)

        # Act
        removed = release("morning", state_path=state_path)

        # Assert
        assert removed == 1
        assert is_locked("morning", state_path=state_path) is False

    def test_leaves_other_locks_alone(self, state_path: Path) -> None:
        # Arrange
        acquire("morning", state_path=state_path)
        acquire("other", state_path=state_path)

        # Act
        release("morning", state_path=state_path)

        # Assert
        assert is_locked("other", state_path=state_path) is True

    def test_removes_every_lock_when_name_is_none(self, state_path: Path) -> None:
        # Arrange
        acquire("morning", state_path=state_path)
        acquire("other", state_path=state_path)

        # Act
        removed = release(state_path=state_path)

        # Assert
        assert removed == 2
        assert is_locked("morning", state_path=state_path) is False
        assert is_locked("other", state_path=state_path) is False

    def test_releasing_an_absent_lock_removes_nothing(self, state_path: Path) -> None:
        # Arrange
        acquire("morning", state_path=state_path)

        # Act
        removed = release("absent", state_path=state_path)

        # Assert
        assert removed == 0

    def test_release_on_missing_file_is_a_no_op(self, state_path: Path) -> None:
        # Arrange
        lock_name = "morning"

        # Act
        removed = release(lock_name, state_path=state_path)

        # Assert
        assert removed == 0

    def test_release_clears_a_corrupt_file(self, state_path: Path) -> None:
        # Arrange
        state_path.write_text("{not json", encoding="utf-8")

        # Act
        release(state_path=state_path)

        # Assert
        assert is_locked("morning", state_path=state_path) is False


class TestAtomicWriteRollback:
    def test_write_failure_leaves_no_temp_file_behind(
        self, state_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        monkeypatch.setattr(module.json, "dump", _boom)

        # Act
        with pytest.raises(RuntimeError) as raised:
            acquire("morning", state_path=state_path)

        # Assert
        assert str(raised.value) == "disk exploded"
        assert list(state_path.parent.glob(".session-locks-*")) == []

    def test_write_failure_survives_a_failing_cleanup(
        self, state_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        monkeypatch.setattr(module.json, "dump", _boom)
        monkeypatch.setattr(module.os, "unlink", _unlink_boom)

        # Act
        with pytest.raises(RuntimeError) as raised:
            acquire("morning", state_path=state_path)

        # Assert
        assert str(raised.value) == "disk exploded"


class TestDefaultStatePath:
    def test_env_var_overrides_the_default(self, custom_lock_state: Path) -> None:
        # Arrange
        expected = custom_lock_state

        # Act
        reloaded = importlib.reload(module)

        # Assert
        assert reloaded.STATE_PATH == expected
