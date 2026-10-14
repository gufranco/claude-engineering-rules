from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.polyglot_mutation_common import (  # noqa: E402
    CommentStyle,
    LineRule,
    body_line_ranges,
    mask_source,
    scan_rules,
)

STATIC_MUT = LineRule(pattern=re.compile(r"\bstatic\s+mut\b"), message="static mut")


def test_mask_source_blanks_c_comments_and_strings():
    # Arrange
    text = 'let a = "static mut"; // static mut\n/* static\nmut */ x\n'

    # Act
    masked = mask_source(text, CommentStyle.C)

    # Assert
    assert ("static" in "\n".join(masked), len(masked)) == (False, 3)


def test_mask_source_blanks_hash_comments_but_keeps_code():
    # Arrange
    text = "FOO = [1] # FOO = [2]\nputs 'x # y'\n"

    # Act
    masked = mask_source(text, CommentStyle.HASH)

    # Assert
    assert [line.rstrip() for line in masked] == ["FOO = [1]", "puts '     '"]


def test_mask_source_blanks_lua_comments():
    # Arrange
    text = "x = 1 -- y = 2\n--[[ z = 3\n]] w = 4\n"

    # Act
    masked = mask_source(text, CommentStyle.LUA)

    # Assert
    assert [line.strip() for line in masked] == ["x = 1", "", "w = 4"]


def test_scan_rules_reports_each_matching_line():
    # Arrange
    text = "static mut A: u8 = 0;\nstatic B: u8 = 0;\nstatic mut C: u8 = 0;\n"

    # Act
    hits = scan_rules(text, CommentStyle.C, (STATIC_MUT,))

    # Assert
    assert [hit.line for hit in hits] == [1, 3]


def test_scan_rules_honors_a_native_suppression_directive():
    # Arrange
    text = "#[allow(static_mut_refs)]\nstatic mut A: u8 = 0;\nstatic mut B: u8 = 0; // NOLINT\n"

    # Act
    hits = scan_rules(text, CommentStyle.C, (STATIC_MUT,))

    # Assert
    assert hits == ()


def test_scan_rules_applies_the_unless_exemption():
    # Arrange
    rule = LineRule(
        pattern=re.compile(r"\[\]\s*=\s*\{"),
        message="mutable table",
        unless=re.compile(r"\bvolatile\b"),
    )
    text = "u8 a[] = {1};\nvolatile u8 b[] = {1};\n"

    # Act
    hits = scan_rules(text, CommentStyle.C, (rule,))

    # Assert
    assert [hit.line for hit in hits] == [1]


def test_body_line_ranges_follows_braces():
    # Arrange
    masked = [
        "record Point {",
        "  int x;",
        "  if (a) { b; }",
        "}",
        "class Other {",
        "}",
    ]

    # Act
    ranges = body_line_ranges(masked, re.compile(r"\brecord\b"))

    # Assert
    assert ranges == [(0, 3)]


def test_mask_source_keeps_a_hash_glued_to_code():
    # Arrange
    text = "echo $# args\n"

    # Act
    masked = mask_source(text, CommentStyle.HASH)

    # Assert
    assert masked == ["echo $# args"]


def test_body_line_ranges_runs_to_the_end_of_an_open_body():
    # Arrange
    masked = ["record Point {", "  int x;"]

    # Act
    ranges = body_line_ranges(masked, re.compile(r"\brecord\b"))

    # Assert
    assert ranges == [(0, 1)]
