from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib.mutation_fix_lookup import (  # noqa: E402
    detector_code_to_mmb,
    fix_suggestions_enabled,
    suggest_fix,
)

TABLE_PATH = REPO_ROOT / "hooks" / "mutation_fix_suggestions.json"
ARRAY_PUSH_FIX = (
    "Replace `arr.push(item)` with `[...arr, item]` or "
    "`Array.from({ length: arr.length + 1 }, (_, i) => i < arr.length ? arr[i] : item)`. "
    "ES2023 `arr.with(arr.length, item)` is read-only and does not extend; "
    "spread is the canonical replacement."
)
ARRAY_POP_FIX = (
    "Replace `arr.pop()` with `arr.slice(0, -1)`. "
    "Use `arr.at(-1)` to read the last value without removing it."
)
ARRAY_SORT_FIX = (
    "Replace `arr.sort(cmp)` with the ES2023 non-mutating `arr.toSorted(cmp)`."
)
DATE_SETTER_FIX = (
    "Date setters mutate the receiver. Use date-fns immutable helpers "
    "(`addMonths`, `subMonths`, `setMonth(d, m)`) or, when the file already uses "
    "Temporal, `Temporal.PlainDate.from(d).with({ ... })`."
)
ARRAY_CATEGORY_FIX = (
    "Array prototype mutation. Use the ES2023 non-mutating equivalents "
    "(`toSorted`, `toReversed`, `toSpliced`, `with`) or spread into a new array."
)
PROPERTY_INCREMENT_FIX = (
    "Postfix increment (`obj.count++`) mutates the receiver. "
    "Use `{ ...obj, count: obj.count + 1 }`."
)


def _exact_table() -> dict[str, dict[str, str]]:
    return json.loads(TABLE_PATH.read_text(encoding="utf-8"))["exact"]


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MUTATION_METHOD_FIX_SUGGESTIONS", raising=False)
    monkeypatch.delenv("MUTATION_METHOD_TC39_STAGE_FILTER", raising=False)


@pytest.mark.parametrize(
    ("detector_code", "expected"),
    [
        ("array.push", ARRAY_PUSH_FIX),
        ("array.pop", ARRAY_POP_FIX),
        ("array.sort", ARRAY_SORT_FIX),
        ("property.increment", PROPERTY_INCREMENT_FIX),
    ],
)
def test_exact_detector_returns_its_table_fix(
    detector_code: str, expected: str
) -> None:
    # Arrange
    code = detector_code

    # Act
    suggestion = suggest_fix(code)

    # Assert
    assert suggestion == expected


@pytest.mark.parametrize(
    "detector_code",
    [
        "collection.map.set",
        "collection.weakmap.set",
        "let.could-be-const",
        "global.assignment",
        "param.reassign",
        "typed-array.set",
        "typed-array.fill",
    ],
)
def test_exact_detector_returns_the_fix_stored_for_it(detector_code: str) -> None:
    # Arrange
    expected = _exact_table()[detector_code]["fix"]

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion == expected


@pytest.mark.parametrize(
    "rule_id", ["date.setMonth", "date.setHours", "date.setUTCFullYear"]
)
def test_date_setter_resolves_via_category_prefix(rule_id: str) -> None:
    # Arrange
    detector = rule_id

    # Act
    suggestion = suggest_fix(detector)

    # Assert
    assert suggestion == DATE_SETTER_FIX


def test_array_bracket_dispatch_resolves_via_category() -> None:
    # Arrange
    detector_code = "array.bracket-dispatch.push"

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion == ARRAY_CATEGORY_FIX


def test_unknown_detector_returns_none(faker: Faker) -> None:
    # Arrange
    detector_code = f"{faker.uuid4()}.{faker.word()}"

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion is None


def test_empty_detector_returns_none() -> None:
    # Arrange
    detector_code = ""

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion is None


@pytest.mark.parametrize(
    "disabled_value", ["0", "false", "False", "FALSE", "no", "off"]
)
def test_env_var_disables_suggestions(
    monkeypatch: pytest.MonkeyPatch, disabled_value: str
) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_FIX_SUGGESTIONS", disabled_value)

    # Act
    suggestion = suggest_fix("array.push")

    # Assert
    assert suggestion is None


@pytest.mark.parametrize(
    "disabled_value", ["0", "false", "False", "FALSE", "no", "off"]
)
def test_env_var_reports_suggestions_disabled(
    monkeypatch: pytest.MonkeyPatch, disabled_value: str
) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_FIX_SUGGESTIONS", disabled_value)

    # Act
    enabled = fix_suggestions_enabled()

    # Assert
    assert enabled is False


@pytest.mark.parametrize("enabled_value", ["1", "true", "yes", "on"])
def test_env_var_enabled_returns_suggestions(
    monkeypatch: pytest.MonkeyPatch, enabled_value: str
) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_FIX_SUGGESTIONS", enabled_value)

    # Act
    suggestion = suggest_fix("array.push")

    # Assert
    assert suggestion == ARRAY_PUSH_FIX


def test_default_env_state_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.delenv("MUTATION_METHOD_FIX_SUGGESTIONS", raising=False)

    # Act
    enabled = fix_suggestions_enabled()

    # Assert
    assert enabled is True


def test_stage_three_entry_is_hidden_by_the_default_stage_filter() -> None:
    # Arrange
    detector_code = "async-iterator.helper-collect"

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion is None


def test_stage_three_entry_carries_a_volatility_prefix_when_opted_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_TC39_STAGE_FILTER", "3")
    detector_code = "async-iterator.helper-collect"
    fix = _exact_table()[detector_code]["fix"]

    # Act
    suggestion = suggest_fix(detector_code)

    # Assert
    assert suggestion == f"[Stage 3 proposal, semantics may evolve] {fix}"


def test_mmb_code_for_array_push() -> None:
    # Arrange
    detector_code = "array.push"

    # Act
    code = detector_code_to_mmb(detector_code)

    # Assert
    assert code == "MMB001"


def test_mmb_code_for_dynamic_date_setter() -> None:
    # Arrange
    detector_code = "date.setMonth"

    # Act
    code = detector_code_to_mmb(detector_code)

    # Assert
    assert code == "MMB027"


@pytest.mark.parametrize(
    ("rule_id", "code"), [("typed-array.set", "MMB021"), ("typed-array.fill", "MMB022")]
)
def test_mmb_code_for_typed_array_dynamic(rule_id: str, code: str) -> None:
    # Arrange
    detector = rule_id

    # Act
    result = detector_code_to_mmb(detector)

    # Assert
    assert result == code


def test_mmb_code_unknown_returns_none(faker: Faker) -> None:
    # Arrange
    detector_code = f"{faker.uuid4()}.{faker.word()}"

    # Act
    code = detector_code_to_mmb(detector_code)

    # Assert
    assert code is None


def test_mmb_codes_have_unique_exact_values() -> None:
    # Arrange
    exact = _exact_table()

    # Act
    codes = [entry["code"] for entry in exact.values()]

    # Assert
    assert len(codes) == len(set(codes)), f"duplicate MMB codes: {codes}"


def test_every_exact_entry_has_code_category_fix() -> None:
    # Arrange
    exact = _exact_table()

    # Act
    malformed = [
        tag
        for tag, entry in exact.items()
        if not (
            entry.get("code", "").startswith("MMB")
            and "category" in entry
            and len(entry.get("fix", "")) > 20
        )
    ]

    # Assert
    assert malformed == []
