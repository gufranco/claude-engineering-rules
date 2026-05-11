"""Extra coverage for `scripts/mutation_fix_lookup.py`.

Targets the module-load error paths (`OSError`, `JSONDecodeError`) and the
empty-input early returns in `_category_lookup` and `detector_code_to_mmb`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _reset_module():
    if "mutation_fix_lookup" in sys.modules:
        del sys.modules["mutation_fix_lookup"]


@pytest.fixture(autouse=True)
def _ensure_clean_module():
    yield
    _reset_module()
    import mutation_fix_lookup  # noqa: F401, E402


def test_load_table_short_circuits_when_already_loaded() -> None:
    # Arrange
    import mutation_fix_lookup as fl  # noqa: WPS433

    fl._TABLE = {"_meta": {}, "exact": {"foo": {"code": "X", "fix": "y"}}}
    fl._EXACT = fl._TABLE["exact"]

    # Act
    fl._load_table()

    # Assert
    assert fl._TABLE["exact"]["foo"]["code"] == "X"


def test_load_table_handles_missing_file(monkeypatch, tmp_path: Path) -> None:
    # Arrange
    _reset_module()
    missing = tmp_path / "missing.json"
    import mutation_fix_lookup as fl  # noqa: WPS433

    fl._TABLE = {}
    fl._EXACT = {}
    fl._BY_CATEGORY = {}
    monkeypatch.setattr(fl, "_FIX_TABLE_PATH", missing)

    # Act
    fl._load_table()

    # Assert
    assert fl._EXACT == {}
    assert fl._BY_CATEGORY == {}
    assert fl._TABLE.get("exact") == {}


def test_load_table_handles_invalid_json(monkeypatch, tmp_path: Path) -> None:
    # Arrange
    _reset_module()
    bad = tmp_path / "bad.json"
    bad.write_text("not json {", encoding="utf-8")
    import mutation_fix_lookup as fl  # noqa: WPS433

    fl._TABLE = {}
    fl._EXACT = {}
    fl._BY_CATEGORY = {}
    monkeypatch.setattr(fl, "_FIX_TABLE_PATH", bad)

    # Act
    fl._load_table()

    # Assert
    assert fl._EXACT == {}
    assert fl._BY_CATEGORY == {}


def test_category_lookup_returns_none_for_empty() -> None:
    # Arrange
    import mutation_fix_lookup as fl  # noqa: WPS433

    # Act
    result = fl._category_lookup("")

    # Assert
    assert result is None


def test_detector_code_to_mmb_returns_none_for_empty() -> None:
    # Arrange
    import mutation_fix_lookup as fl  # noqa: WPS433

    # Act
    result = fl.detector_code_to_mmb("")

    # Assert
    assert result is None
