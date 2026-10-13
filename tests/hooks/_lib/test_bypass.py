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

from _lib.bypass import WILDCARD, is_bypassed  # noqa: E402
from _lib.bypass_writer import (  # noqa: E402
    DEFAULT_TTL_SECONDS,
    MIN_TTL_SECONDS,
    clear_bypass,
    set_bypass,
)


@pytest.fixture()
def state_path(tmp_path: Path) -> Path:
    return tmp_path / ".bypass-state.json"


def _write_raw(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def boom(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("disk full")


class TestIsBypassed:
    def test_returns_false_when_file_missing(self, state_path: Path) -> None:
        # Arrange
        text = "any-hook"

        # Act
        result = is_bypassed(text, state_path=state_path)

        # Assert
        assert result is False

    def test_returns_false_when_file_malformed(self, state_path: Path) -> None:
        # Arrange
        state_path.write_text("not json{{", encoding="utf-8")

        # Act
        result = is_bypassed("any-hook", state_path=state_path)

        # Assert
        assert result is False

    def test_returns_false_when_root_not_object(self, state_path: Path) -> None:
        # Arrange
        _write_raw(state_path, [1, 2, 3])

        # Act
        result = is_bypassed("any-hook", state_path=state_path)

        # Assert
        assert result is False

    def test_returns_false_when_bypasses_not_list(self, state_path: Path) -> None:
        # Arrange
        _write_raw(state_path, {"version": 1, "bypasses": "not-a-list"})

        # Act
        result = is_bypassed("any-hook", state_path=state_path)

        # Assert
        assert result is False

    def test_returns_false_for_empty_hook_name(self, state_path: Path) -> None:
        # Arrange
        text = ""

        # Act
        result = is_bypassed(text, state_path=state_path)

        # Assert
        assert result is False

    def test_skips_non_dict_entries(self, state_path: Path) -> None:
        # Arrange
        _write_raw(state_path, {"version": 1, "bypasses": ["string", 42, None]})

        # Act
        result = is_bypassed("any", state_path=state_path)

        # Assert
        assert result is False

    def test_skips_entries_with_invalid_expiry_type(self, state_path: Path) -> None:
        # Arrange
        _write_raw(
            state_path, {"version": 1, "bypasses": [{"hook": "h", "expires_at": 12345}]}
        )

        # Act
        result = is_bypassed("h", state_path=state_path)

        # Assert
        assert result is False

    def test_skips_entries_with_unparseable_expiry_string(
        self, state_path: Path
    ) -> None:
        # Arrange
        _write_raw(
            state_path,
            {"version": 1, "bypasses": [{"hook": "h", "expires_at": "yesterday"}]},
        )

        # Act
        result = is_bypassed("h", state_path=state_path)

        # Assert
        assert result is False

    def test_skips_entries_missing_expiry(self, state_path: Path) -> None:
        # Arrange
        _write_raw(state_path, {"version": 1, "bypasses": [{"hook": "h"}]})

        # Act
        result = is_bypassed("h", state_path=state_path)

        # Assert
        assert result is False

    def test_returns_true_for_exact_match_within_ttl(self, state_path: Path) -> None:
        # Arrange
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        _write_raw(
            state_path,
            {"version": 1, "bypasses": [{"hook": "h", "expires_at": future}]},
        )

        # Act
        result = is_bypassed("h", state_path=state_path)

        # Assert
        assert result is True

    def test_returns_false_for_expired_entry(self, state_path: Path) -> None:
        # Arrange
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        _write_raw(
            state_path, {"version": 1, "bypasses": [{"hook": "h", "expires_at": past}]}
        )

        # Act
        result = is_bypassed("h", state_path=state_path)

        # Assert
        assert result is False

    def test_wildcard_entry_matches_any_hook(self, state_path: Path) -> None:
        # Arrange
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        _write_raw(
            state_path,
            {"version": 1, "bypasses": [{"hook": WILDCARD, "expires_at": future}]},
        )

        # Act
        result = is_bypassed("anything", state_path=state_path)

        # Assert
        assert result is True

    def test_non_matching_hook_returns_false(self, state_path: Path) -> None:
        # Arrange
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        _write_raw(
            state_path,
            {"version": 1, "bypasses": [{"hook": "other", "expires_at": future}]},
        )

        # Act
        result = is_bypassed("h", state_path=state_path)

        # Assert
        assert result is False

    def test_accepts_z_suffix_iso_timestamp(self, state_path: Path) -> None:
        # Arrange
        future = (
            (datetime.now(timezone.utc) + timedelta(minutes=5))
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        _write_raw(
            state_path,
            {"version": 1, "bypasses": [{"hook": "h", "expires_at": future}]},
        )

        # Act
        result = is_bypassed("h", state_path=state_path)

        # Assert
        assert result is True

    def test_naive_timestamp_treated_as_utc(self, state_path: Path) -> None:
        # Arrange
        future = (
            (datetime.now(timezone.utc) + timedelta(minutes=5))
            .replace(tzinfo=None)
            .isoformat()
        )
        _write_raw(
            state_path,
            {"version": 1, "bypasses": [{"hook": "h", "expires_at": future}]},
        )

        # Act
        result = is_bypassed("h", state_path=state_path)

        # Assert
        assert result is True

    def test_uses_module_default_path_when_none_supplied(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Arrange
        default = tmp_path / ".bypass-state.json"
        monkeypatch.setattr("_lib.bypass.STATE_PATH", default)
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        _write_raw(
            default, {"version": 1, "bypasses": [{"hook": "h", "expires_at": future}]}
        )

        # Act
        result = is_bypassed("h")

        # Assert
        assert result is True

    @pytest.mark.parametrize(("minutes", "expected"), [(0, True), (3, False)])
    def test_uses_supplied_now_for_ttl_math(
        self, state_path: Path, minutes: int, expected: bool
    ) -> None:
        # Arrange
        fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        expires_at = (fixed + timedelta(minutes=2)).isoformat()
        _write_raw(
            state_path,
            {"version": 1, "bypasses": [{"hook": "h", "expires_at": expires_at}]},
        )

        # Act
        bypassed = is_bypassed(
            "h", state_path=state_path, now=fixed + timedelta(minutes=minutes)
        )

        # Assert
        assert bypassed is expected

    @pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses chmod")
    def test_unreadable_file_returns_false(self, state_path: Path) -> None:
        # Arrange
        state_path.write_text("{}", encoding="utf-8")
        state_path.chmod(0o000)

        # Act
        result = is_bypassed("h", state_path=state_path)

        # Assert
        assert result is False


class TestSetBypass:
    def test_creates_file_with_mode_0600(self, state_path: Path) -> None:
        # Arrange
        hook = "h"

        # Act
        set_bypass(hook, state_path=state_path)

        # Assert
        assert stat.S_IMODE(state_path.stat().st_mode) == 0o600

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        # Arrange
        path = tmp_path / "nested" / "deeper" / "state.json"

        # Act
        set_bypass("h", state_path=path)

        # Assert
        assert path.exists() is True

    def test_clamps_ttl_to_minimum(self, state_path: Path) -> None:
        # Arrange
        fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)

        # Act
        set_bypass("h", ttl_seconds=10, state_path=state_path, now=fixed)

        # Assert
        data = json.loads(state_path.read_text(encoding="utf-8"))
        expires = datetime.fromisoformat(data["bypasses"][0]["expires_at"])
        assert (expires - fixed).total_seconds() == MIN_TTL_SECONDS

    def test_clamps_ttl_to_maximum(self, state_path: Path) -> None:
        # Arrange
        fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)

        # Act
        set_bypass("h", ttl_seconds=99999, state_path=state_path, now=fixed)

        # Assert
        data = json.loads(state_path.read_text(encoding="utf-8"))
        expires = datetime.fromisoformat(data["bypasses"][0]["expires_at"])
        assert (expires - fixed).total_seconds() == 3600

    def test_default_ttl_used_when_unspecified(self, state_path: Path) -> None:
        # Arrange
        fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)

        # Act
        set_bypass("h", state_path=state_path, now=fixed)

        # Assert
        data = json.loads(state_path.read_text(encoding="utf-8"))
        expires = datetime.fromisoformat(data["bypasses"][0]["expires_at"])
        assert (expires - fixed).total_seconds() == DEFAULT_TTL_SECONDS

    def test_wildcard_ttl_capped_lower(self, state_path: Path) -> None:
        # Arrange
        fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cap = 1200

        # Act
        set_bypass(WILDCARD, ttl_seconds=99999, state_path=state_path, now=fixed)

        # Assert
        data = json.loads(state_path.read_text(encoding="utf-8"))
        expires = datetime.fromisoformat(data["bypasses"][0]["expires_at"])
        assert (expires - fixed).total_seconds() == cap

    def test_reason_persisted_when_supplied(self, state_path: Path) -> None:
        # Arrange
        hook = "h"

        # Act
        set_bypass(hook, reason="debug ticket 42", state_path=state_path)

        # Assert
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert data["bypasses"][0]["reason"] == "debug ticket 42"

    def test_reason_omitted_when_none(self, state_path: Path) -> None:
        # Arrange
        hook = "h"

        # Act
        set_bypass(hook, state_path=state_path)

        # Assert
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert "reason" not in data["bypasses"][0]

    def test_replaces_existing_entry_for_same_hook(self, state_path: Path) -> None:
        # Arrange
        set_bypass("h", reason="first", state_path=state_path)

        # Act
        set_bypass("h", reason="second", state_path=state_path)

        # Assert
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert len(data["bypasses"]) == 1
        assert data["bypasses"][0]["reason"] == "second"

    def test_preserves_entries_for_other_hooks(self, state_path: Path) -> None:
        # Arrange
        set_bypass("a", state_path=state_path)

        # Act
        set_bypass("b", state_path=state_path)

        # Assert
        data = json.loads(state_path.read_text(encoding="utf-8"))
        hooks = {entry["hook"] for entry in data["bypasses"]}
        assert hooks == {"a", "b"}

    def test_empty_hook_name_raises(self, state_path: Path) -> None:
        # Arrange
        hook = ""

        # Act
        with pytest.raises(ValueError) as raised:
            set_bypass(hook, state_path=state_path)

        # Assert
        assert str(raised.value) == "hook name is required"

    def test_recovers_when_existing_file_malformed(self, state_path: Path) -> None:
        # Arrange
        state_path.write_text("garbage", encoding="utf-8")

        # Act
        set_bypass("h", state_path=state_path)

        # Assert
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert data["version"] == 1
        assert data["bypasses"][0]["hook"] == "h"

    def test_recovers_when_existing_file_wrong_version(self, state_path: Path) -> None:
        # Arrange
        state_path.write_text(
            json.dumps({"version": 99, "bypasses": [{"hook": "x"}]}), encoding="utf-8"
        )

        # Act
        set_bypass("h", state_path=state_path)

        # Assert
        data = json.loads(state_path.read_text(encoding="utf-8"))
        hooks = {entry["hook"] for entry in data["bypasses"]}
        assert hooks == {"h"}

    def test_filters_non_dict_existing_entries(self, state_path: Path) -> None:
        # Arrange
        state_path.write_text(
            json.dumps({"version": 1, "bypasses": ["bad", {"hook": "good"}]}),
            encoding="utf-8",
        )

        # Act
        set_bypass("h", state_path=state_path)

        # Assert
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert {entry.get("hook") for entry in data["bypasses"]} == {"good", "h"}

    def test_uses_module_default_path_when_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Arrange
        default = tmp_path / "state.json"
        monkeypatch.setattr("_lib.bypass_writer.STATE_PATH", default)

        # Act
        result = set_bypass("h")

        # Assert
        assert result == default
        assert default.exists() is True

    def test_uses_now_default_when_unspecified(self, state_path: Path) -> None:
        # Arrange
        ttl_seconds = 600

        # Act
        set_bypass("h", ttl_seconds=ttl_seconds, state_path=state_path)

        # Assert
        data = json.loads(state_path.read_text(encoding="utf-8"))
        expires = datetime.fromisoformat(data["bypasses"][0]["expires_at"])
        delta = (expires - datetime.now(timezone.utc)).total_seconds()
        assert 590 <= delta <= 610

    def test_atomic_write_cleans_tempfile_on_failure(
        self, monkeypatch: pytest.MonkeyPatch, state_path: Path
    ) -> None:
        # Arrange
        monkeypatch.setattr("_lib.bypass_writer.os.replace", boom)

        # Act
        with pytest.raises(RuntimeError) as raised:
            set_bypass("h", state_path=state_path)

        # Assert
        leftovers = [
            p
            for p in state_path.parent.iterdir()
            if p.name.startswith(".bypass-state.")
        ]
        assert str(raised.value) == "disk full"
        assert leftovers == []


class TestClearBypass:
    def test_returns_zero_when_file_missing(self, state_path: Path) -> None:
        # Arrange
        hook = "h"

        # Act
        result = clear_bypass(hook, state_path=state_path)

        # Assert
        assert result == 0

    def test_removes_single_hook(self, state_path: Path) -> None:
        # Arrange
        set_bypass("a", state_path=state_path)
        set_bypass("b", state_path=state_path)

        # Act
        removed = clear_bypass("a", state_path=state_path)

        # Assert
        assert removed == 1
        data = json.loads(state_path.read_text(encoding="utf-8"))
        hooks = {entry["hook"] for entry in data["bypasses"]}
        assert hooks == {"b"}

    def test_removes_all_when_hook_is_none(self, state_path: Path) -> None:
        # Arrange
        set_bypass("a", state_path=state_path)
        set_bypass("b", state_path=state_path)

        # Act
        removed = clear_bypass(None, state_path=state_path)

        # Assert
        assert removed == 2
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert data["bypasses"] == []

    def test_returns_zero_when_no_matching_hook(self, state_path: Path) -> None:
        # Arrange
        set_bypass("a", state_path=state_path)

        # Act
        result = clear_bypass("missing", state_path=state_path)

        # Assert
        assert result == 0

    def test_no_write_when_nothing_removed(self, state_path: Path) -> None:
        # Arrange
        set_bypass("a", state_path=state_path)
        mtime_before = state_path.stat().st_mtime_ns

        # Act
        clear_bypass("missing", state_path=state_path)

        # Assert
        assert state_path.stat().st_mtime_ns == mtime_before

    def test_uses_module_default_path_when_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Arrange
        default = tmp_path / "state.json"
        monkeypatch.setattr("_lib.bypass.STATE_PATH", default)
        monkeypatch.setattr("_lib.bypass_writer.STATE_PATH", default)
        set_bypass("h")

        # Act
        removed = clear_bypass("h")

        # Assert
        assert removed == 1
