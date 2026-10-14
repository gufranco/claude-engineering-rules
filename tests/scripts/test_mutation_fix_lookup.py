from __future__ import annotations

import sys
from pathlib import Path

import pytest
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_fix_lookup import tc39_stage_filter  # noqa: E402

STAGE_FILTER_VAR = "MUTATION_METHOD_TC39_STAGE_FILTER"


def test_stage_filter_defaults_to_four_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.delenv(STAGE_FILTER_VAR, raising=False)

    # Act
    stage = tc39_stage_filter()

    # Assert
    assert stage == 4


@pytest.mark.parametrize(("raw", "expected"), [("2", 2), ("3", 3), ("4", 4)])
def test_stage_filter_returns_an_in_range_value_unchanged(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: int
) -> None:
    # Arrange
    monkeypatch.setenv(STAGE_FILTER_VAR, raw)

    # Act
    stage = tc39_stage_filter()

    # Assert
    assert stage == expected


@pytest.mark.parametrize(("raw", "expected"), [("1", 2), ("-7", 2), ("9", 4)])
def test_stage_filter_clamps_out_of_range_values(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: int
) -> None:
    # Arrange
    monkeypatch.setenv(STAGE_FILTER_VAR, raw)

    # Act
    stage = tc39_stage_filter()

    # Assert
    assert stage == expected


def test_stage_filter_falls_back_to_four_for_a_non_integer(
    monkeypatch: pytest.MonkeyPatch, faker: Faker
) -> None:
    # Arrange
    monkeypatch.setenv(STAGE_FILTER_VAR, faker.word())

    # Act
    stage = tc39_stage_filter()

    # Assert
    assert stage == 4
