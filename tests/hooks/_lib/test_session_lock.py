"""Tests for `hooks/_lib/session_lock.py`.

Target: 100% coverage. The allow paths matter as much as the block paths,
because a lock that never lifts silently breaks `/deploy land`.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.session_lock import (  # noqa: E402
    DEFAULT_TTL_SECONDS,
    MAX_TTL_SECONDS,
    MIN_TTL_SECONDS,
    WILDCARD,
    acquire,
    is_locked,
    release,
)


@pytest.fixture()
def state_path(tmp_path: Path) -> Path:
    return tmp_path / ".session-locks.json"


def _write_raw(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _future(seconds: int = 600) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _past(seconds: int = 600) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


class TestIsLockedUnlockedPaths:
    def test_missing_file_reads_as_unlocked(self, state_path: Path) -> None:
        result = is_locked("morning", state_path=state_path)

        assert result is False

    def test_empty_lock_name_reads_as_unlocked(self, state_path: Path) -> None:
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": WILDCARD, "expires_at": _future()}]},
        )

        result = is_locked("", state_path=state_path)

        assert result is False

    def test_absent_locks_key_reads_as_unlocked(self, state_path: Path) -> None:
        _write_raw(state_path, {"version": 1})

        result = is_locked("morning", state_path=state_path)

        assert result is False

    def test_expired_entry_reads_as_unlocked(self, state_path: Path) -> None:
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "morning", "expires_at": _past()}]},
        )

        result = is_locked("morning", state_path=state_path)

        assert result is False

    def test_other_lock_name_reads_as_unlocked(self, state_path: Path) -> None:
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "other", "expires_at": _future()}]},
        )

        result = is_locked("morning", state_path=state_path)

        assert result is False

    def test_entry_without_expiry_is_ignored(self, state_path: Path) -> None:
        _write_raw(state_path, {"version": 1, "locks": [{"lock": "morning"}]})

        result = is_locked("morning", state_path=state_path)

        assert result is False

    def test_unparseable_expiry_is_ignored(self, state_path: Path) -> None:
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "morning", "expires_at": "not-a-date"}]},
        )

        result = is_locked("morning", state_path=state_path)

        assert result is False

    def test_non_dict_entries_are_skipped(self, state_path: Path) -> None:
        _write_raw(state_path, {"version": 1, "locks": ["garbage", 42]})

        result = is_locked("morning", state_path=state_path)

        assert result is False


class TestIsLockedLockedPaths:
    def test_live_entry_reads_as_locked(self, state_path: Path) -> None:
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "morning", "expires_at": _future()}]},
        )

        result = is_locked("morning", state_path=state_path)

        assert result is True

    def test_wildcard_entry_matches_any_lock(self, state_path: Path) -> None:
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": WILDCARD, "expires_at": _future()}]},
        )

        result = is_locked("morning", state_path=state_path)

        assert result is True

    def test_naive_expiry_is_treated_as_utc(self, state_path: Path) -> None:
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

        result = is_locked("morning", state_path=state_path)

        assert result is True

    def test_zulu_suffix_expiry_parses(self, state_path: Path) -> None:
        stamp = (datetime.now(timezone.utc) + timedelta(seconds=600)).replace(
            microsecond=0
        )
        raw = stamp.isoformat().replace("+00:00", "Z")
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "morning", "expires_at": raw}]},
        )

        result = is_locked("morning", state_path=state_path)

        assert result is True

    def test_explicit_now_controls_the_comparison(self, state_path: Path) -> None:
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "morning", "expires_at": _future(60)}]},
        )

        result = is_locked(
            "morning",
            state_path=state_path,
            now=datetime.now(timezone.utc) + timedelta(seconds=3600),
        )

        assert result is False


class TestIsLockedFailsClosed:
    def test_malformed_json_reads_as_locked(self, state_path: Path) -> None:
        state_path.write_text("{not json", encoding="utf-8")

        result = is_locked("morning", state_path=state_path)

        assert result is True

    def test_non_object_root_reads_as_locked(self, state_path: Path) -> None:
        _write_raw(state_path, ["not", "an", "object"])

        result = is_locked("morning", state_path=state_path)

        assert result is True

    def test_non_list_locks_reads_as_locked(self, state_path: Path) -> None:
        _write_raw(state_path, {"version": 1, "locks": {"lock": "morning"}})

        result = is_locked("morning", state_path=state_path)

        assert result is True

    def test_unreadable_file_reads_as_locked(self, state_path: Path) -> None:
        _write_raw(state_path, {"version": 1, "locks": []})
        state_path.chmod(0o000)

        try:
            if os.geteuid() == 0:
                pytest.skip("root bypasses file permissions")
            result = is_locked("morning", state_path=state_path)
        finally:
            state_path.chmod(0o600)

        assert result is True


class TestAcquire:
    def test_creates_a_live_entry(self, state_path: Path) -> None:
        acquire("morning", state_path=state_path, reason="daily sweep")

        assert is_locked("morning", state_path=state_path) is True

    def test_rejects_an_empty_lock_name(self, state_path: Path) -> None:
        with pytest.raises(ValueError):
            acquire("", state_path=state_path)

    def test_writes_owner_only_permissions(self, state_path: Path) -> None:
        acquire("morning", state_path=state_path)

        mode = stat.S_IMODE(state_path.stat().st_mode)

        assert mode == 0o600

    def test_records_the_reason(self, state_path: Path) -> None:
        acquire("morning", state_path=state_path, reason="daily sweep")

        payload = json.loads(state_path.read_text(encoding="utf-8"))

        assert payload["locks"][0]["reason"] == "daily sweep"

    def test_defaults_the_reason_to_empty(self, state_path: Path) -> None:
        acquire("morning", state_path=state_path)

        payload = json.loads(state_path.read_text(encoding="utf-8"))

        assert payload["locks"][0]["reason"] == ""

    def test_clamps_ttl_below_the_floor(self, state_path: Path) -> None:
        acquire("morning", state_path=state_path, ttl_seconds=1)

        payload = json.loads(state_path.read_text(encoding="utf-8"))
        expires = datetime.fromisoformat(payload["locks"][0]["expires_at"])
        remaining = (expires - datetime.now(timezone.utc)).total_seconds()

        assert remaining > MIN_TTL_SECONDS - 5

    def test_clamps_ttl_above_the_ceiling(self, state_path: Path) -> None:
        acquire("morning", state_path=state_path, ttl_seconds=999999)

        payload = json.loads(state_path.read_text(encoding="utf-8"))
        expires = datetime.fromisoformat(payload["locks"][0]["expires_at"])
        remaining = (expires - datetime.now(timezone.utc)).total_seconds()

        assert remaining <= MAX_TTL_SECONDS + 5

    def test_replaces_an_existing_entry_for_the_same_lock(
        self, state_path: Path
    ) -> None:
        acquire("morning", state_path=state_path, ttl_seconds=DEFAULT_TTL_SECONDS)
        acquire("morning", state_path=state_path, ttl_seconds=DEFAULT_TTL_SECONDS)

        payload = json.loads(state_path.read_text(encoding="utf-8"))

        assert len(payload["locks"]) == 1

    def test_preserves_a_different_live_lock(self, state_path: Path) -> None:
        acquire("morning", state_path=state_path)
        acquire("other", state_path=state_path)

        assert is_locked("morning", state_path=state_path) is True
        assert is_locked("other", state_path=state_path) is True

    def test_drops_expired_entries_on_write(self, state_path: Path) -> None:
        _write_raw(
            state_path,
            {"version": 1, "locks": [{"lock": "stale", "expires_at": _past()}]},
        )

        acquire("morning", state_path=state_path)

        payload = json.loads(state_path.read_text(encoding="utf-8"))
        names = [entry["lock"] for entry in payload["locks"]]

        assert names == ["morning"]

    def test_recovers_from_a_corrupt_file(self, state_path: Path) -> None:
        state_path.write_text("{not json", encoding="utf-8")

        acquire("morning", state_path=state_path)

        assert is_locked("morning", state_path=state_path) is True

    def test_creates_missing_parent_directories(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested" / ".session-locks.json"

        acquire("morning", state_path=nested)

        assert nested.exists()


class TestRelease:
    def test_removes_the_named_lock(self, state_path: Path) -> None:
        acquire("morning", state_path=state_path)

        removed = release("morning", state_path=state_path)

        assert removed == 1
        assert is_locked("morning", state_path=state_path) is False

    def test_leaves_other_locks_alone(self, state_path: Path) -> None:
        acquire("morning", state_path=state_path)
        acquire("other", state_path=state_path)

        release("morning", state_path=state_path)

        assert is_locked("other", state_path=state_path) is True

    def test_removes_every_lock_when_name_is_none(self, state_path: Path) -> None:
        acquire("morning", state_path=state_path)
        acquire("other", state_path=state_path)

        removed = release(state_path=state_path)

        assert removed == 2
        assert is_locked("morning", state_path=state_path) is False
        assert is_locked("other", state_path=state_path) is False

    def test_releasing_an_absent_lock_removes_nothing(self, state_path: Path) -> None:
        acquire("morning", state_path=state_path)

        removed = release("absent", state_path=state_path)

        assert removed == 0

    def test_release_on_missing_file_is_a_no_op(self, state_path: Path) -> None:
        removed = release("morning", state_path=state_path)

        assert removed == 0

    def test_release_clears_a_corrupt_file(self, state_path: Path) -> None:
        state_path.write_text("{not json", encoding="utf-8")

        release(state_path=state_path)

        assert is_locked("morning", state_path=state_path) is False


class TestAtomicWriteRollback:
    def test_write_failure_leaves_no_temp_file_behind(
        self, state_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import _lib.session_lock as module

        def _boom(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("disk exploded")

        monkeypatch.setattr(module.json, "dump", _boom)

        with pytest.raises(RuntimeError):
            acquire("morning", state_path=state_path)

        leftovers = list(state_path.parent.glob(".session-locks-*"))

        assert leftovers == []

    def test_write_failure_survives_a_failing_cleanup(
        self, state_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import _lib.session_lock as module

        def _boom(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("disk exploded")

        def _unlink_boom(*_args: object, **_kwargs: object) -> None:
            raise OSError("cleanup denied")

        monkeypatch.setattr(module.json, "dump", _boom)
        monkeypatch.setattr(module.os, "unlink", _unlink_boom)

        with pytest.raises(RuntimeError):
            acquire("morning", state_path=state_path)


class TestDefaultStatePath:
    def test_env_var_overrides_the_default(self, tmp_path: Path) -> None:
        target = tmp_path / "custom-locks.json"
        os.environ["CLAUDE_SESSION_LOCK_STATE"] = str(target)

        try:
            import importlib

            import _lib.session_lock as module

            reloaded = importlib.reload(module)
            assert reloaded.STATE_PATH == target
        finally:
            del os.environ["CLAUDE_SESSION_LOCK_STATE"]
            import importlib

            import _lib.session_lock as module

            importlib.reload(module)
