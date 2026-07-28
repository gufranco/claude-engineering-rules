"""Extra coverage for `scripts/mutation_fix_lookup.py`.

Targets the module-load error paths (`OSError`, `JSONDecodeError`) and the
empty-input early returns in `_category_lookup` and `detector_code_to_mmb`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture(autouse=True)
def _restore_table_globals():
    """Restore the module-level lookup cache after every test in this file.

    `_load_table()` memoizes into `_TABLE`, `_EXACT`, and `_BY_CATEGORY`. The
    tests below overwrite those to exercise the load error paths. Without a
    restore, every later test sharing the worker sees an empty table and
    `suggest_fix` returns None, which surfaces as an order-dependent failure.
    """
    from _lib import mutation_fix_lookup as fl

    saved = (fl._TABLE, fl._EXACT, fl._BY_CATEGORY)
    yield
    fl._TABLE, fl._EXACT, fl._BY_CATEGORY = saved


def test_load_table_short_circuits_when_already_loaded(monkeypatch) -> None:
    from _lib import mutation_fix_lookup as fl  # noqa: WPS433

    monkeypatch.setattr(
        fl, "_TABLE", {"_meta": {}, "exact": {"foo": {"code": "X", "fix": "y"}}}
    )
    monkeypatch.setattr(fl, "_EXACT", fl._TABLE["exact"])

    fl._load_table()

    assert fl._TABLE["exact"]["foo"]["code"] == "X"


def test_load_table_handles_missing_file(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    from _lib import mutation_fix_lookup as fl  # noqa: WPS433

    monkeypatch.setattr(fl, "_TABLE", {})
    monkeypatch.setattr(fl, "_EXACT", {})
    monkeypatch.setattr(fl, "_BY_CATEGORY", {})
    monkeypatch.setattr(fl, "_FIX_TABLE_PATH", missing)

    fl._load_table()

    assert fl._EXACT == {}
    assert fl._BY_CATEGORY == {}
    assert fl._TABLE.get("exact") == {}


def test_load_table_handles_invalid_json(monkeypatch, tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json {", encoding="utf-8")
    from _lib import mutation_fix_lookup as fl  # noqa: WPS433

    monkeypatch.setattr(fl, "_TABLE", {})
    monkeypatch.setattr(fl, "_EXACT", {})
    monkeypatch.setattr(fl, "_BY_CATEGORY", {})
    monkeypatch.setattr(fl, "_FIX_TABLE_PATH", bad)

    fl._load_table()

    assert fl._EXACT == {}
    assert fl._BY_CATEGORY == {}


def test_category_lookup_returns_none_for_empty() -> None:
    from _lib import mutation_fix_lookup as fl  # noqa: WPS433

    result = fl._category_lookup("")

    assert result is None


def test_detector_code_to_mmb_returns_none_for_empty() -> None:
    from _lib import mutation_fix_lookup as fl  # noqa: WPS433

    result = fl.detector_code_to_mmb("")

    assert result is None
