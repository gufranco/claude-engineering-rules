"""Confidence scoring tests.

Plan items 265-267. Verifies the public API of `scripts/mutation_confidence.py`:

  - Score range is [1, 10] for every input combination.
  - Canonical detectors with AST + typed receiver score 10.
  - Heuristic detectors max out at 7 even with full evidence.
  - SARIF level mapping matches the documented thresholds.
  - clamp() coerces out-of-range scores back into [1, 10].
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from mutation_confidence import (  # noqa: E402
    CONFIDENCE_HIGH,
    clamp,
    score_finding,
    to_sarif_level,
)


def test_canonical_with_ast_and_typed_receiver_scores_10():
    score = score_finding(
        "array.push", ast_confirmed=True, receiver_known=True, file_path="src/a.ts"
    )
    assert score == CONFIDENCE_HIGH


def test_canonical_with_ast_and_unknown_receiver_scores_high_but_not_max():
    score = score_finding(
        "array.push", ast_confirmed=True, receiver_known=False, file_path="src/a.ts"
    )
    assert 7 <= score < CONFIDENCE_HIGH


def test_canonical_without_ast_falls_through_to_regex_band():
    score = score_finding(
        "array.push", ast_confirmed=False, receiver_known=False, file_path="src/a.ts"
    )
    assert 5 <= score <= 7


def test_heuristic_detector_caps_below_canonical_max():
    score = score_finding(
        "object.assign-with-non-fresh-target",
        ast_confirmed=True,
        receiver_known=True,
        file_path="src/a.ts",
    )
    assert score < CONFIDENCE_HIGH


def test_score_within_documented_range_for_all_combinations():
    for ast in (True, False):
        for known in (True, False):
            for detector in ("array.push", "let.could.be.const"):
                score = score_finding(
                    detector,
                    ast_confirmed=ast,
                    receiver_known=known,
                    file_path="src/a.ts",
                )
                assert 1 <= score <= 10


def test_to_sarif_level_thresholds():
    assert to_sarif_level(10) == "error"
    assert to_sarif_level(5) == "error"
    assert to_sarif_level(4) == "warning"
    assert to_sarif_level(3) == "warning"
    assert to_sarif_level(2) == "note"
    assert to_sarif_level(1) == "note"


def test_clamp_within_range():
    assert clamp(7) == 7
    assert clamp(1) == 1
    assert clamp(10) == 10


def test_clamp_below_range_to_one():
    assert clamp(-5) == 1
    assert clamp(0) == 1


def test_clamp_above_range_to_ten():
    assert clamp(42) == 10
    assert clamp(11) == 10


def test_collection_map_set_canonical_with_full_evidence():
    score = score_finding(
        "collection.map.set",
        ast_confirmed=True,
        receiver_known=True,
        file_path="src/a.ts",
    )
    assert score == CONFIDENCE_HIGH


def test_typed_array_set_canonical_with_typed_suffix():
    score = score_finding(
        "typed-array.set",
        ast_confirmed=False,
        receiver_known=True,
        file_path="src/a.ts",
    )
    assert score >= 5


def test_unknown_detector_falls_back_to_low_score():
    score = score_finding(
        "made.up.tag",
        ast_confirmed=False,
        receiver_known=False,
        file_path="src/a.ts",
    )
    assert score <= 4
