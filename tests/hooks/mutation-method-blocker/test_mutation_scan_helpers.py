from __future__ import annotations

import re
import sys
from pathlib import Path

from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_scan_helpers import (  # noqa: E402
    NamedWriteSpec,
    collect_names,
    is_inside_open_call,
    iter_masked_lines,
    iter_stripped_lines,
    looks_like_declaration,
    make_match,
    masked_lookback,
    name_alternation,
    scan_named_writes,
)


def _identifier(faker: Faker) -> str:
    return faker.pystr(min_chars=4, max_chars=8).lower()


def test_iter_stripped_lines_skips_blank_lines_and_strips_comments() -> None:
    # Arrange
    text = "a.push(1) // trailing\n\n  \nb = 'x'\n"

    # Act
    rows = iter_stripped_lines(text)

    # Assert
    assert rows == [
        (1, "a.push(1) // trailing", "a.push(1)            "),
        (4, "b = 'x'", "b = ' '"),
    ]


def test_iter_masked_lines_masks_a_multi_line_template_literal() -> None:
    # Arrange
    text = "const q = `\nobj.x = 1\n`;\n"

    # Act
    rows = iter_masked_lines(text)

    # Assert
    assert rows == [
        (1, "const q = `", "const q = `"),
        (2, "obj.x = 1", "         "),
        (3, "`;", "`;"),
    ]


def test_make_match_converts_the_column_to_one_based_and_truncates(
    faker: Faker,
) -> None:
    # Arrange
    raw = "x" * 130
    hint = faker.sentence()

    # Act
    match = make_match("demo.detector", 3, 4, raw, hint)

    # Assert
    assert (match.line, match.col, match.detector, match.fix_hint) == (
        3,
        5,
        "demo.detector",
        hint,
    )
    assert match.text == "x" * 120 + "..."
    assert match.metadata == {}


def test_looks_like_declaration_accepts_a_typed_field_and_rejects_an_assignment() -> (
    None
):
    # Arrange
    field = "  count: number"
    assignment = "obj.count = 1"

    # Act
    verdicts = (
        looks_like_declaration(field, field),
        looks_like_declaration(assignment, assignment),
    )

    # Assert
    assert verdicts == (True, False)


def test_name_alternation_escapes_every_name() -> None:
    # Arrange
    names = ("$store",)

    # Act
    alternation = name_alternation(names)

    # Assert
    assert alternation == r"\$store"


def test_collect_names_returns_every_named_group(faker: Faker) -> None:
    # Arrange
    first, second = _identifier(faker), _identifier(faker) + "b"
    pattern = re.compile(r"let (?P<name>\w+)")

    # Act
    names = collect_names(pattern, f"let {first}; let {second};")

    # Assert
    assert names == frozenset({first, second})


def test_masked_lookback_masks_strings_in_the_preceding_window() -> None:
    # Arrange
    lines = ["a('x')", "b()"]

    # Act
    window = masked_lookback(lines, 2)

    # Assert
    assert window == "a(' ')\nb()"


def test_masked_lookback_is_empty_before_the_first_line() -> None:
    # Arrange
    lines: list[str] = []

    # Act
    window = masked_lookback(lines, 0)

    # Assert
    assert window == ""


def test_is_inside_open_call_detects_an_unclosed_opener() -> None:
    # Arrange
    masked = "run(() => {\n  x = 1"

    # Act
    verdicts = (
        is_inside_open_call(masked, "run("),
        is_inside_open_call("run(() => 1)", "run("),
        is_inside_open_call(masked, "other("),
    )

    # Assert
    assert verdicts == (True, False, False)


def test_scan_named_writes_skips_declarations_and_rejected_matches(
    faker: Faker,
) -> None:
    # Arrange
    name = _identifier(faker)
    text = f"const {name} = make();\n{name}.value = 1;\n{name}.other = 2;\n"
    spec = NamedWriteSpec(
        detector="demo.write",
        pattern=re.compile(rf"(?P<name>{name})\.(?P<prop>\w+) ="),
        skip_line=re.compile(r"\bconst\b"),
        fix_hint="hint",
        metadata=lambda m: {"prop": m.group("prop")},
        accepts=lambda m, _lineno: m.group("prop") == "value",
    )

    # Act
    matches = scan_named_writes(text, spec)

    # Assert
    assert [(m.line, m.col, m.metadata) for m in matches] == [(2, 1, {"prop": "value"})]
