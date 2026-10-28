from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.coverage_exclusion import (  # noqa: E402
    Action,
    added_lines,
    inline_exclusions,
    is_coverage_config,
    thresholds,
    verdict_for,
)

NO_COVER = "# " + "prag" + "ma: no cover"
DIRECTIVES = [
    NO_COVER,
    "# " + "prag" + "ma: no branch",
    "/* " + "istan" + "bul ignore next */",
    "/* c" + "8 ignore next */",
    "/* v" + "8 ignore start */",
    "// node:coverage " + "disable",
    "// coverage:" + "ignore-line",
    "#[cover" + "age(off)]",
    "[ExcludeFrom" + "CodeCoverage]",
    "@codeCoverage" + "Ignore",
    "// LCOV_" + "EXCL_LINE",
    "# :no" + "cov:",
]


@pytest.mark.parametrize("directive", DIRECTIVES)
def test_every_exclusion_form_is_counted(directive):
    # Arrange
    text = f"x = 1  {directive}\n"

    # Act
    result = inline_exclusions(text)

    # Assert
    assert result == 1


def test_adding_a_directive_to_source_is_blocked():
    # Arrange
    before = "def f():\n    return 1\n"
    after = f"def f():\n    return 1  {NO_COVER}\n"

    # Act
    result = verdict_for("/repo/src/app.py", before, after)

    # Assert
    assert (result.action, result.problems) == (
        Action.BLOCK,
        ("adds 1 coverage exclusion directive",),
    )


def test_adding_two_directives_names_the_plural():
    # Arrange
    after = f"a = 1  {NO_COVER}\nb = 2  {NO_COVER}\n"

    # Act
    result = verdict_for("/repo/src/app.py", "", after)

    # Assert
    assert result.problems == ("adds 2 coverage exclusion directives",)


def test_removing_a_directive_is_allowed():
    # Arrange
    before = f"x = 1  {NO_COVER}\n"

    # Act
    result = verdict_for("/repo/src/app.py", before, "x = 1\n")

    # Assert
    assert result.action is Action.ALLOW


def test_prose_files_may_name_directives():
    # Arrange
    after = f"Never write `{NO_COVER}`.\n"

    # Act
    result = verdict_for("/repo/docs/testing.md", "", after)

    # Assert
    assert result.action is Action.ALLOW


@pytest.mark.parametrize(
    "path",
    [
        "/repo/.coveragerc",
        "/repo/pyproject.toml",
        "/repo/vitest.config.ts",
        "/repo/jest.config.js",
        "/repo/.github/workflows/ci.yml",
        "/repo/Makefile",
    ],
)
def test_coverage_configs_are_recognised(path):
    # Arrange
    candidate = path

    # Act
    result = is_coverage_config(candidate)

    # Assert
    assert result is True


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("fail_under = 95", [95.0]),
        ("--cov-fail-under=100", [100.0]),
        ("coverage report --fail-under 90", [90.0]),
        ("node --test --test-coverage-lines=80", [80.0]),
        ("c8 --lines 70", [70.0]),
        ('"branches": 85,', [85.0]),
        ("thresholds: { functions: 99.5 }", [99.5]),
        ("minimum_coverage 60", [60.0]),
        ("target: 75%", [75.0]),
        ("timeout = 30", []),
    ],
)
def test_thresholds_read_each_tool_syntax(text, expected):
    # Arrange
    source = text

    # Act
    result = thresholds(source)

    # Assert
    assert result == expected


def test_writing_a_threshold_under_100_is_blocked():
    # Arrange
    before = "[report]\nshow_missing = True\n"
    after = "[report]\nfail_under = 95\nshow_missing = True\n"

    # Act
    result = verdict_for("/repo/.coveragerc", before, after)

    # Assert
    assert (result.action, result.problems) == (
        Action.BLOCK,
        ("line 2 sets a coverage threshold of 95, below 100",),
    )


def test_deleting_the_only_100_threshold_line_is_not_lowering():
    # Arrange
    before = "[report]\nfail_under = 100\n"

    # Act
    result = verdict_for("/repo/.coveragerc", before, "[report]\n")

    # Assert
    assert result.action is Action.ALLOW


def test_lowering_100_to_a_fraction_below_is_blocked():
    # Arrange
    before = "--cov-fail-under=100\n"
    after = "--cov-fail-under=99.9\n"

    # Act
    result = verdict_for("/repo/Makefile", before, after)

    # Assert
    assert result.problems == ("line 1 sets a coverage threshold of 99.9, below 100",)


def test_raising_a_threshold_to_100_is_allowed():
    # Arrange
    before = "[report]\nfail_under = 95\n"
    after = "[report]\nfail_under = 100\n"

    # Act
    result = verdict_for("/repo/.coveragerc", before, after)

    # Assert
    assert result.action is Action.ALLOW


def test_an_omit_entry_asks_for_confirmation():
    # Arrange
    before = "[run]\nomit =\n    */generated/*\n"
    after = "[run]\nomit =\n    */generated/*\n    */hooks/new_hook.py\n"

    # Act
    result = verdict_for("/repo/.coveragerc", before, after)

    # Assert
    assert (result.action, result.problems) == (
        Action.ASK,
        ("line 4: */hooks/new_hook.py",),
    )


def test_an_unrelated_config_change_is_allowed():
    # Arrange
    before = '{\n  "name": "web"\n}\n'
    after = '{\n  "name": "web",\n  "private": true\n}\n'

    # Act
    result = verdict_for("/repo/package.json", before, after)

    # Assert
    assert result.action is Action.ALLOW


def test_added_lines_reports_replacements_and_inserts():
    # Arrange
    before = "a\nb\nc\n"
    after = "a\nB\nc\nd\n"

    # Act
    result = added_lines(before, after)

    # Assert
    assert result == [(1, "B"), (3, "d")]
