from __future__ import annotations

import sys
from pathlib import Path

from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_detectors_bindings import (  # noqa: E402
    canonical_static_block_line_ranges,
    detect_let_could_be_const,
    detect_param_reassignment,
    detect_static_block_mutation,
    filter_matches_in_canonical_static_blocks,
)
from _lib.mutation_detectors_core import Match  # noqa: E402


def _source(faker: Faker) -> str:
    return f"/repo/src/{faker.word()}.ts"


def test_param_reassignment_flags_a_reassigned_parameter(faker: Faker) -> None:
    # Arrange
    text = "function update(opts) {\n  opts = {};\n}\n"

    # Act
    hits = detect_param_reassignment(text, "ts", _source(faker))

    # Assert
    assert [(h.line, h.metadata["name"]) for h in hits] == [(2, "opts")]


def test_param_reassignment_skips_allowlisted_names(faker: Faker) -> None:
    # Arrange
    text = "function handle(event) {\n  event = null;\n}\n"

    # Act
    hits = detect_param_reassignment(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_let_could_be_const_flags_only_unreassigned_bindings(faker: Faker) -> None:
    # Arrange
    text = "let a = 1;\nlet b = 2;\nb += 1;\nfor (let i = 0; i < 2; i++) {}\n"

    # Act
    hits = detect_let_could_be_const(text, "ts", _source(faker))

    # Assert
    assert [(h.line, h.metadata["name"]) for h in hits] == [(1, "a")]


def test_static_block_with_branching_is_flagged(faker: Faker) -> None:
    # Arrange
    text = "class Box {\n  static {\n    if (x) { y(); }\n  }\n}\n"

    # Act
    hits = detect_static_block_mutation(text, "ts", _source(faker))

    # Assert
    assert [(h.line, h.metadata["reason"]) for h in hits] == [
        (2, "branching inside static block")
    ]


def test_second_static_block_in_one_class_is_flagged(faker: Faker) -> None:
    # Arrange
    text = "class Box {\n  static {\n    a = 1;\n  }\n  static {\n    b = 2;\n  }\n}\n"

    # Act
    hits = detect_static_block_mutation(text, "ts", _source(faker))

    # Assert
    assert [(h.line, h.metadata["reason"]) for h in hits] == [
        (5, "multiple static blocks per class")
    ]


def test_canonical_static_block_ranges_cover_a_single_sequential_block() -> None:
    # Arrange
    text = "class Box {\n  static {\n    Box.x = 1;\n  }\n}\n"

    # Act
    ranges = canonical_static_block_line_ranges(text)

    # Assert
    assert ranges == [(2, 4)]


def test_filter_drops_property_writes_inside_a_canonical_block() -> None:
    # Arrange
    text = "class Box {\n  static {\n    Box.x = 1;\n  }\n}\nBox.y = 2;\n"
    inside = Match(line=3, col=5, text="Box.x = 1;", detector="property.assignment")
    outside = Match(line=6, col=1, text="Box.y = 2;", detector="property.assignment")
    other = Match(line=3, col=5, text="Box.x = 1;", detector="array.push")

    # Act
    kept = filter_matches_in_canonical_static_blocks([inside, outside, other], text)

    # Assert
    assert kept == [outside, other]
