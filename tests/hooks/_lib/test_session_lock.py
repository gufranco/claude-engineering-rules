from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from _helpers.session_lock_support import (
    DEFAULT_TTL_SECONDS,
    MAX_TTL_SECONDS,
    MIN_TTL_SECONDS,
    WILDCARD,
    acquire,
    is_locked,
)


def _write_raw(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _future(seconds: int = 600) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _past(seconds: int = 600) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


class TestIsLockedUnlockedPaths:
    def test_missing_file_reads_as_unlocked(self, state_path: Path) -> None:
        # Arrange
        lock_name = "morning"

        # Act
        result = is_locked(lock_name, state_path=state_path)

        # Assert
        assert result is False

    def test_empty_lock_name_reads_as_unlocked(self, state_path: Path) -> None:
        # Arrange
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": WILDCARD, "expires_at": _future()}]},
        )

        # Act
        result = is_locked("", state_path=state_path)

        # Assert
        assert result is False

    def test_absent_locks_key_reads_as_unlocked(self, state_path: Path) -> None:
        # Arrange
        _write_raw(state_path, {"version": 1})

        # Act
        result = is_locked("morning", state_path=state_path)

        # Assert
        assert result is False

    def test_expired_entry_reads_as_unlocked(self, state_path: Path) -> None:
        # Arrange
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "morning", "expires_at": _past()}]},
        )

        # Act
        result = is_locked("morning", state_path=state_path)

        # Assert
        assert result is False

    def test_other_lock_name_reads_as_unlocked(self, state_path: Path) -> None:
        # Arrange
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "other", "expires_at": _future()}]},
        )

        # Act
        result = is_locked("morning", state_path=state_path)

        # Assert
        assert result is False

    def test_entry_without_expiry_is_ignored(self, state_path: Path) -> None:
        # Arrange
        _write_raw(state_path, {"version": 1, "locks": [{"lock": "morning"}]})

        # Act
        result = is_locked("morning", state_path=state_path)

        # Assert
        assert result is False

    def test_unparseable_expiry_is_ignored(self, state_path: Path) -> None:
        # Arrange
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "morning", "expires_at": "not-a-date"}]},
        )

        # Act
        result = is_locked("morning", state_path=state_path)

        # Assert
        assert result is False

    def test_non_dict_entries_are_skipped(self, state_path: Path) -> None:
        # Arrange
        _write_raw(state_path, {"version": 1, "locks": ["garbage", 42]})

        # Act
        result = is_locked("morning", state_path=state_path)

        # Assert
        assert result is False


class TestIsLockedLockedPaths:
    def test_live_entry_reads_as_locked(self, state_path: Path) -> None:
        # Arrange
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "morning", "expires_at": _future()}]},
        )

        # Act
        result = is_locked("morning", state_path=state_path)

        # Assert
        assert result is True

    def test_wildcard_entry_matches_any_lock(self, state_path: Path) -> None:
        # Arrange
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": WILDCARD, "expires_at": _future()}]},
        )

        # Act
        result = is_locked("morning", state_path=state_path)

        # Assert
        assert result is True

    def test_naive_expiry_is_treated_as_utc(self, state_path: Path) -> None:
        # Arrange
        naive = (datetime.now(timezone.utc) + timedelta(seconds=600)).replace(
            tzinfo=None
        )
        _write_raw(
            state_path,
            {
                "version": 1,
                "locks": [{"lock": "morning", "expires_at": naive.isoformat()}],
            },
        )

        # Act
        result = is_locked("morning", state_path=state_path)

        # Assert
        assert result is True

    def test_zulu_suffix_expiry_parses(self, state_path: Path) -> None:
        # Arrange
        stamp = (datetime.now(timezone.utc) + timedelta(seconds=600)).replace(
            microsecond=0
        )
        raw = stamp.isoformat().replace("+00:00", "Z")
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "morning", "expires_at": raw}]},
        )

        # Act
        result = is_locked("morning", state_path=state_path)

        # Assert
        assert result is True

    def test_explicit_now_controls_the_comparison(self, state_path: Path) -> None:
        # Arrange
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "morning", "expires_at": _future(60)}]},
        )

        # Act
        result = is_locked(
            "morning",
            state_path=state_path,
            now=datetime.now(timezone.utc) + timedelta(seconds=3600),
        )

        # Assert
        assert result is False


class TestIsLockedFailsClosed:
    def test_malformed_json_reads_as_locked(self, state_path: Path) -> None:
        # Arrange
        state_path.write_text("{not json", encoding="utf-8")

        # Act
        result = is_locked("morning", state_path=state_path)

        # Assert
        assert result is True

    def test_non_object_root_reads_as_locked(self, state_path: Path) -> None:
        # Arrange
        _write_raw(state_path, ["not", "an", "object"])

        # Act
        result = is_locked("morning", state_path=state_path)

        # Assert
        assert result is True

    def test_non_list_locks_reads_as_locked(self, state_path: Path) -> None:
        # Arrange
        _write_raw(state_path, {"version": 1, "locks": {"lock": "morning"}})

        # Act
        result = is_locked("morning", state_path=state_path)

        # Assert
        assert result is True

    @pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses file permissions")
    def test_unreadable_file_reads_as_locked(self, state_path: Path) -> None:
        # Arrange
        _write_raw(state_path, {"version": 1, "locks": []})
        state_path.chmod(0o000)

        # Act
        result = is_locked("morning", state_path=state_path)

        # Assert
        assert result is True


class TestAcquire:
    def test_creates_a_live_entry(self, state_path: Path) -> None:
        # Arrange
        lock_name = "morning"

        # Act
        acquire(lock_name, state_path=state_path, reason="daily sweep")

        # Assert
        assert is_locked("morning", state_path=state_path) is True

    def test_rejects_an_empty_lock_name(self, state_path: Path) -> None:
        # Arrange
        lock_name = ""

        # Act
        with pytest.raises(ValueError) as raised:
            acquire(lock_name, state_path=state_path)

        # Assert
        assert str(raised.value) == "lock_name is required"

    def test_writes_owner_only_permissions(self, state_path: Path) -> None:
        # Arrange
        lock_name = "morning"

        # Act
        acquire(lock_name, state_path=state_path)

        # Assert
        assert stat.S_IMODE(state_path.stat().st_mode) == 0o600

    def test_records_the_reason(self, state_path: Path) -> None:
        # Arrange
        lock_name = "morning"

        # Act
        acquire(lock_name, state_path=state_path, reason="daily sweep")

        # Assert
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        assert payload["locks"][0]["reason"] == "daily sweep"

    def test_defaults_the_reason_to_empty(self, state_path: Path) -> None:
        # Arrange
        lock_name = "morning"

        # Act
        acquire(lock_name, state_path=state_path)

        # Assert
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        assert payload["locks"][0]["reason"] == ""

    def test_clamps_ttl_below_the_floor(self, state_path: Path) -> None:
        # Arrange
        ttl_seconds = 1

        # Act
        acquire("morning", state_path=state_path, ttl_seconds=ttl_seconds)

        # Assert
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        expires = datetime.fromisoformat(payload["locks"][0]["expires_at"])
        remaining = (expires - datetime.now(timezone.utc)).total_seconds()
        assert remaining > MIN_TTL_SECONDS - 5

    def test_clamps_ttl_above_the_ceiling(self, state_path: Path) -> None:
        # Arrange
        ttl_seconds = 999999

        # Act
        acquire("morning", state_path=state_path, ttl_seconds=ttl_seconds)

        # Assert
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        expires = datetime.fromisoformat(payload["locks"][0]["expires_at"])
        remaining = (expires - datetime.now(timezone.utc)).total_seconds()
        assert remaining <= MAX_TTL_SECONDS + 5

    def test_replaces_an_existing_entry_for_the_same_lock(
        self, state_path: Path
    ) -> None:
        # Arrange
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "morning", "expires_at": _future()}]},
        )

        # Act
        acquire("morning", state_path=state_path, ttl_seconds=DEFAULT_TTL_SECONDS)

        # Assert
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        assert len(payload["locks"]) == 1

    def test_preserves_a_different_live_lock(self, state_path: Path) -> None:
        # Arrange
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "morning", "expires_at": _future()}]},
        )

        # Act
        acquire("other", state_path=state_path)

        # Assert
        assert is_locked("morning", state_path=state_path) is True
        assert is_locked("other", state_path=state_path) is True

    def test_drops_expired_entries_on_write(self, state_path: Path) -> None:
        # Arrange
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "stale", "expires_at": _past()}]},
        )

        # Act
        acquire("morning", state_path=state_path)

        # Assert
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        names = [entry["lock"] for entry in payload["locks"]]
        assert names == ["morning"]

    def test_recovers_from_a_corrupt_file(self, state_path: Path) -> None:
        # Arrange
        state_path.write_text("{not json", encoding="utf-8")

        # Act
        acquire("morning", state_path=state_path)

        # Assert
        assert is_locked("morning", state_path=state_path) is True

    def test_creates_missing_parent_directories(self, tmp_path: Path) -> None:
        # Arrange
        nested = tmp_path / "deep" / "nested" / ".session-locks.json"

        # Act
        acquire("morning", state_path=nested)

        # Assert
        assert nested.exists()
