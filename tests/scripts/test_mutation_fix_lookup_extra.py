from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import mutation_fix_lookup as fl  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_table_globals():
    saved = (fl._TABLE, fl._EXACT, fl._BY_CATEGORY)
    yield
    fl._TABLE, fl._EXACT, fl._BY_CATEGORY = saved


def test_load_table_short_circuits_when_already_loaded(monkeypatch) -> None:
    # Arrange
    monkeypatch.setattr(
        fl, "_TABLE", {"_meta": {}, "exact": {"foo": {"code": "X", "fix": "y"}}}
    )
    monkeypatch.setattr(fl, "_EXACT", fl._TABLE["exact"])

    # Act
    fl._load_table()

    # Assert
    assert fl._TABLE["exact"]["foo"]["code"] == "X"


def test_load_table_handles_missing_file(monkeypatch, tmp_path: Path) -> None:
    # Arrange
    missing = tmp_path / "missing.json"
    monkeypatch.setattr(fl, "_TABLE", {})
    monkeypatch.setattr(fl, "_EXACT", {})
    monkeypatch.setattr(fl, "_BY_CATEGORY", {})
    monkeypatch.setattr(fl, "_FIX_TABLE_PATH", missing)

    # Act
    fl._load_table()

    # Assert
    assert fl._EXACT == {}
    assert fl._BY_CATEGORY == {}
    assert fl._TABLE.get("exact") == {}


def test_load_table_handles_invalid_json(monkeypatch, tmp_path: Path) -> None:
    # Arrange
    bad = tmp_path / "bad.json"
    bad.write_text("not json {", encoding="utf-8")
    monkeypatch.setattr(fl, "_TABLE", {})
    monkeypatch.setattr(fl, "_EXACT", {})
    monkeypatch.setattr(fl, "_BY_CATEGORY", {})
    monkeypatch.setattr(fl, "_FIX_TABLE_PATH", bad)

    # Act
    fl._load_table()

    # Assert
    assert fl._EXACT == {}
    assert fl._BY_CATEGORY == {}


def test_category_lookup_returns_none_for_empty() -> None:
    # Arrange
    detector = ""

    # Act
    result = fl._category_lookup(detector)

    # Assert
    assert result is None


def test_detector_code_to_mmb_returns_none_for_empty() -> None:
    # Arrange
    code = ""

    # Act
    result = fl.detector_code_to_mmb(code)

    # Assert
    assert result is None
