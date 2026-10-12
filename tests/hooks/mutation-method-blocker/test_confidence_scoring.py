from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.mutation_confidence import (  # noqa: E402
    CONFIDENCE_HIGH,
    clamp,
    score_finding,
    to_sarif_level,
)


def test_canonical_with_ast_and_typed_receiver_scores_10():
    # Arrange
    detector = "array.push"

    # Act
    score = score_finding(
        detector, ast_confirmed=True, receiver_known=True, file_path="src/a.ts"
    )

    # Assert
    assert score == CONFIDENCE_HIGH


def test_canonical_with_ast_and_unknown_receiver_scores_high_but_not_max():
    # Arrange
    detector = "array.push"

    # Act
    score = score_finding(
        detector, ast_confirmed=True, receiver_known=False, file_path="src/a.ts"
    )

    # Assert
    assert 7 <= score < CONFIDENCE_HIGH


def test_canonical_without_ast_falls_through_to_regex_band():
    # Arrange
    detector = "array.push"

    # Act
    score = score_finding(
        detector, ast_confirmed=False, receiver_known=False, file_path="src/a.ts"
    )

    # Assert
    assert 5 <= score <= 7


def test_heuristic_detector_caps_below_canonical_max():
    # Arrange
    detector = "object.assign-with-non-fresh-target"

    # Act
    score = score_finding(
        detector,
        ast_confirmed=True,
        receiver_known=True,
        file_path="src/a.ts",
    )

    # Assert
    assert score < CONFIDENCE_HIGH


@pytest.mark.parametrize("ast_confirmed", [True, False])
@pytest.mark.parametrize("receiver_known", [True, False])
@pytest.mark.parametrize("detector", ["array.push", "let.could.be.const"])
def test_score_within_documented_range_for_all_combinations(
    ast_confirmed, receiver_known, detector
):
    # Arrange
    file_path = "src/a.ts"

    # Act
    score = score_finding(
        detector,
        ast_confirmed=ast_confirmed,
        receiver_known=receiver_known,
        file_path=file_path,
    )

    # Assert
    assert 1 <= score <= 10


@pytest.mark.parametrize(
    ("score", "level"),
    [
        (10, "error"),
        (5, "error"),
        (4, "warning"),
        (3, "warning"),
        (2, "note"),
        (1, "note"),
    ],
)
def test_to_sarif_level_thresholds(score, level):
    # Arrange
    confidence = score

    # Act
    result = to_sarif_level(confidence)

    # Assert
    assert result == level


@pytest.mark.parametrize("value", [7, 1, 10])
def test_clamp_within_range(value):
    # Arrange
    raw = value

    # Act
    result = clamp(raw)

    # Assert
    assert result == value


@pytest.mark.parametrize("value", [-5, 0])
def test_clamp_below_range_to_one(value):
    # Arrange
    raw = value

    # Act
    result = clamp(raw)

    # Assert
    assert result == 1


@pytest.mark.parametrize("value", [42, 11])
def test_clamp_above_range_to_ten(value):
    # Arrange
    raw = value

    # Act
    result = clamp(raw)

    # Assert
    assert result == 10


def test_collection_map_set_canonical_with_full_evidence():
    # Arrange
    detector = "collection.map.set"

    # Act
    score = score_finding(
        detector,
        ast_confirmed=True,
        receiver_known=True,
        file_path="src/a.ts",
    )

    # Assert
    assert score == CONFIDENCE_HIGH


def test_typed_array_set_canonical_with_typed_suffix():
    # Arrange
    detector = "typed-array.set"

    # Act
    score = score_finding(
        detector,
        ast_confirmed=False,
        receiver_known=True,
        file_path="src/a.ts",
    )

    # Assert
    assert score >= 5


def test_unknown_detector_falls_back_to_low_score():
    # Arrange
    detector = "made.up.tag"

    # Act
    score = score_finding(
        detector,
        ast_confirmed=False,
        receiver_known=False,
        file_path="src/a.ts",
    )

    # Assert
    assert score <= 4
