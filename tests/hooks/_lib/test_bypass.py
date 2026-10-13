from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass import WILDCARD, is_bypassed  # noqa: E402


@pytest.fixture()
def state_path(tmp_path: Path) -> Path:
    return tmp_path / ".bypass-state.json"


def _write_raw(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


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
