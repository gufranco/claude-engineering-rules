from __future__ import annotations

import json
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
    # Arrange
    detector_code = "array.push"

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion is not None
    assert "[...arr, item]" in suggestion


def test_array_pop_exact_match():
    # Arrange
    detector_code = "array.pop"

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion is not None
    assert "slice(0, -1)" in suggestion


def test_array_sort_uses_to_sorted():
    # Arrange
    detector_code = "array.sort"

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion is not None
    assert "toSorted" in suggestion


def test_collection_map_set_exact_match():
    # Arrange
    detector_code = "collection.map.set"

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion is not None
    assert "new Map" in suggestion


@pytest.mark.parametrize(
    "rule_id", ["date.setMonth", "date.setHours", "date.setUTCFullYear"]
)
def test_date_setter_resolves_via_category_prefix(rule_id):
    # Arrange
    detector = rule_id

    # Act
    suggestion = suggest_fix(detector)

    # Assert
    assert suggestion is not None
    assert "date-fns" in suggestion
    assert "Temporal" in suggestion


@pytest.mark.parametrize("rule_id", ["typed-array.set", "typed-array.fill"])
def test_typed_array_dynamic_code_resolves(rule_id):
    # Arrange
    detector = rule_id

    # Act
    suggestion = suggest_fix(detector)

    # Assert
    assert suggestion is not None


def test_array_bracket_dispatch_resolves_via_category():
    # Arrange
    detector_code = "array.bracket-dispatch.push"

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion is not None
    assert "Array prototype" in suggestion or "ES2023" in suggestion


def test_collection_weakmap_set_exact_match():
    # Arrange
    detector_code = "collection.weakmap.set"

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion is not None
    assert "WeakMap" in suggestion


def test_property_increment_exact_match():
    # Arrange
    detector_code = "property.increment"

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion is not None
    assert "+ 1" in suggestion or "+= 1" in suggestion or "..." in suggestion


def test_let_could_be_const_exact_match():
    # Arrange
    detector_code = "let.could-be-const"

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion is not None
    assert "const" in suggestion


def test_global_assignment_exact_match():
    # Arrange
    detector_code = "global.assignment"

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion is not None
    assert "globalThis" in suggestion or "global" in suggestion.lower()


def test_param_reassign_exact_match():
    # Arrange
    detector_code = "param.reassign"

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion is not None


def test_unknown_detector_returns_none():
    # Arrange
    detector_code = "never.heard.of.this"

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion is None


def test_empty_detector_returns_none():
    # Arrange
    detector_code = ""

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion is None


@pytest.mark.parametrize(
    "disabled_value", ["0", "false", "False", "FALSE", "no", "off"]
)
def test_env_var_disables_suggestions(monkeypatch, disabled_value):
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_FIX_SUGGESTIONS", disabled_value)

    # Act
    suggestion = suggest_fix("array.push")

    # Assert
    assert suggestion is None
    assert fix_suggestions_enabled() is False


@pytest.mark.parametrize("enabled_value", ["1", "true", "yes", "on"])
def test_env_var_enabled_returns_suggestions(monkeypatch, enabled_value):
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_FIX_SUGGESTIONS", enabled_value)

    # Act
    suggestion = suggest_fix("array.push")

    # Assert
    assert suggestion is not None
    assert fix_suggestions_enabled() is True


def test_default_env_state_enabled(monkeypatch):
    # Arrange
    monkeypatch.delenv("MUTATION_METHOD_FIX_SUGGESTIONS", raising=False)

    # Act
    enabled = fix_suggestions_enabled()

    # Assert
    assert enabled is True


def test_mmb_code_for_array_push():
    # Arrange
    detector_code = "array.push"

    # Act
    code = detector_code_to_mmb(detector_code)

    # Assert
    assert code == "MMB001"


def test_mmb_code_for_dynamic_date_setter():
    # Arrange
    detector_code = "date.setMonth"

    # Act
    code = detector_code_to_mmb(detector_code)

    # Assert
    assert code == "MMB027"


@pytest.mark.parametrize(
    ("rule_id", "code"), [("typed-array.set", "MMB021"), ("typed-array.fill", "MMB022")]
)
def test_mmb_code_for_typed_array_dynamic(rule_id, code):
    # Arrange
    detector = rule_id

    # Act
    result = detector_code_to_mmb(detector)

    # Assert
    assert result == code


def test_mmb_code_unknown_returns_none():
    # Arrange
    detector_code = "non.existent.code"

    # Act
    code = detector_code_to_mmb(detector_code)

    # Assert
    assert code is None


def _exact_table(table_path: Path) -> dict:
    return json.loads(table_path.read_text(encoding="utf-8"))["exact"]


def test_mmb_codes_have_unique_exact_values():
    # Arrange
    table_path = REPO_ROOT / "hooks" / "mutation_fix_suggestions.json"

    # Act
    exact = _exact_table(table_path)

    # Assert
    codes = [entry["code"] for entry in exact.values()]
    assert len(codes) == len(set(codes)), f"duplicate MMB codes: {codes}"


def test_every_exact_entry_has_code_category_fix():
    # Arrange
    table_path = REPO_ROOT / "hooks" / "mutation_fix_suggestions.json"

    # Act
    exact = _exact_table(table_path)

    # Assert
    malformed = [
        tag
        for tag, entry in exact.items()
        if not (
            entry.get("code", "").startswith("MMB")
            and "category" in entry
            and len(entry.get("fix", "")) > 20
        )
    ]
    assert malformed == []
