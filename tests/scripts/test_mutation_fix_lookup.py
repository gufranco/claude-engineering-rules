"""Unit tests for the fix-suggestion lookup table.

Item 173 of the plan. Verifies:

  - Exact-match resolution for every documented detector tag.
  - Category-prefix fallback for dynamic codes (`date.setMonth`,
    `typed-array.fill`, `collection.weakmap.set`).
  - The env-var gate (`MUTATION_METHOD_FIX_SUGGESTIONS=0`) suppresses output.
  - Stable MMB codes match the JSON registry.
  - Unknown detector codes return `None`.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib.mutation_fix_lookup import (  # noqa: E402
    detector_code_to_mmb,
    fix_suggestions_enabled,
    suggest_fix,
)


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    monkeypatch.delenv("MUTATION_METHOD_FIX_SUGGESTIONS", raising=False)
    yield


def test_array_push_exact_match():
    suggestion = suggest_fix("array.push")

    assert suggestion is not None
    assert "[...arr, item]" in suggestion


def test_array_pop_exact_match():
    suggestion = suggest_fix("array.pop")

    assert suggestion is not None
    assert "slice(0, -1)" in suggestion


def test_array_sort_uses_to_sorted():
    suggestion = suggest_fix("array.sort")

    assert suggestion is not None
    assert "toSorted" in suggestion


def test_collection_map_set_exact_match():
    suggestion = suggest_fix("collection.map.set")

    assert suggestion is not None
    assert "new Map" in suggestion


def test_date_setter_resolves_via_category_prefix():
    suggestion_month = suggest_fix("date.setMonth")
    suggestion_hours = suggest_fix("date.setHours")
    suggestion_year = suggest_fix("date.setUTCFullYear")

    assert suggestion_month is not None
    assert suggestion_hours is not None
    assert suggestion_year is not None
    assert "date-fns" in suggestion_month
    assert "Temporal" in suggestion_month


def test_typed_array_dynamic_code_resolves():
    suggestion_set = suggest_fix("typed-array.set")
    suggestion_fill = suggest_fix("typed-array.fill")

    assert suggestion_set is not None
    assert suggestion_fill is not None


def test_array_bracket_dispatch_resolves_via_category():
    suggestion = suggest_fix("array.bracket-dispatch.push")

    assert suggestion is not None
    assert "Array prototype" in suggestion or "ES2023" in suggestion


def test_collection_weakmap_set_exact_match():
    suggestion = suggest_fix("collection.weakmap.set")

    assert suggestion is not None
    assert "WeakMap" in suggestion


def test_property_increment_exact_match():
    suggestion = suggest_fix("property.increment")

    assert suggestion is not None
    assert "+ 1" in suggestion or "+= 1" in suggestion or "..." in suggestion


def test_let_could_be_const_exact_match():
    suggestion = suggest_fix("let.could-be-const")

    assert suggestion is not None
    assert "const" in suggestion


def test_global_assignment_exact_match():
    suggestion = suggest_fix("global.assignment")

    assert suggestion is not None
    assert "globalThis" in suggestion or "global" in suggestion.lower()


def test_param_reassign_exact_match():
    suggestion = suggest_fix("param.reassign")

    assert suggestion is not None


def test_unknown_detector_returns_none():
    suggestion = suggest_fix("never.heard.of.this")

    assert suggestion is None


def test_empty_detector_returns_none():
    suggestion = suggest_fix("")

    assert suggestion is None


@pytest.mark.parametrize(
    "disabled_value", ["0", "false", "False", "FALSE", "no", "off"]
)
def test_env_var_disables_suggestions(monkeypatch, disabled_value):
    monkeypatch.setenv("MUTATION_METHOD_FIX_SUGGESTIONS", disabled_value)

    suggestion = suggest_fix("array.push")

    assert suggestion is None
    assert fix_suggestions_enabled() is False


@pytest.mark.parametrize("enabled_value", ["1", "true", "yes", "on"])
def test_env_var_enabled_returns_suggestions(monkeypatch, enabled_value):
    monkeypatch.setenv("MUTATION_METHOD_FIX_SUGGESTIONS", enabled_value)

    suggestion = suggest_fix("array.push")

    assert suggestion is not None
    assert fix_suggestions_enabled() is True


def test_default_env_state_enabled():
    if "MUTATION_METHOD_FIX_SUGGESTIONS" in os.environ:
        del os.environ["MUTATION_METHOD_FIX_SUGGESTIONS"]

    enabled = fix_suggestions_enabled()

    assert enabled is True


def test_mmb_code_for_array_push():
    code = detector_code_to_mmb("array.push")

    assert code == "MMB001"


def test_mmb_code_for_dynamic_date_setter():
    code = detector_code_to_mmb("date.setMonth")

    assert code == "MMB027"


def test_mmb_code_for_typed_array_dynamic():
    code_set = detector_code_to_mmb("typed-array.set")
    code_fill = detector_code_to_mmb("typed-array.fill")

    assert code_set == "MMB021"
    assert code_fill == "MMB022"


def test_mmb_code_unknown_returns_none():
    code = detector_code_to_mmb("non.existent.code")

    assert code is None


def test_mmb_codes_have_unique_exact_values():
    import json

    table_path = REPO_ROOT / "hooks" / "mutation_fix_suggestions.json"
    table = json.loads(table_path.read_text(encoding="utf-8"))
    exact = table["exact"]

    codes = [entry["code"] for entry in exact.values()]

    assert len(codes) == len(set(codes)), f"duplicate MMB codes: {codes}"


def test_every_exact_entry_has_code_category_fix():
    import json

    table_path = REPO_ROOT / "hooks" / "mutation_fix_suggestions.json"
    table = json.loads(table_path.read_text(encoding="utf-8"))

    for tag, entry in table["exact"].items():
        assert "code" in entry, f"{tag} missing code"
        assert entry["code"].startswith("MMB"), f"{tag} code does not start with MMB"
        assert "category" in entry, f"{tag} missing category"
        assert "fix" in entry, f"{tag} missing fix"
        assert len(entry["fix"]) > 20, f"{tag} fix is suspiciously short"
