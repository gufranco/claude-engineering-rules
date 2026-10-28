from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from _helpers.lint_skills_support import LINTER, run_linter


def _load():
    spec = importlib.util.spec_from_file_location("lint_skills_units", LINTER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lint = _load()


def test_parse_frontmatter_skips_blank_and_colonless_lines():
    # Arrange
    text = "---\nname: a\n\nloose words\ndescription: d\n  continued\n---\nbody\n"

    # Act
    fields, body = lint.parse_frontmatter(text)

    # Assert
    assert (fields, body) == ({"name": "a", "description": "d continued"}, "body\n")


@pytest.mark.parametrize(
    ("line", "mode", "expected"),
    [
        ("\tname: x", None, ("tab in indentation", None)),
        ("  orphan", None, ("indented line with no parent key", None)),
        ("not a key line", "plain", ("expected a `key: value` line", None)),
    ],
)
def test_line_error_names_each_structural_problem(line, mode, expected):
    # Arrange
    current = mode

    # Act
    result = lint.line_error(line, current)

    # Assert
    assert result == expected


def test_comment_lines_are_skipped_by_both_scanners():
    # Arrange
    raw = "# leading comment\nname: a\n  # indented comment\n"

    # Act
    result = (lint.find_yaml_errors(raw), lint.find_truncating_comments(raw))

    # Assert
    assert result == ([], [])


def test_plain_line_text_ignores_a_non_key_line():
    # Arrange
    line = "not a key"

    # Act
    result = lint.plain_line_text(line, "plain")

    # Assert
    assert result == (None, None)


def test_yaml_findings_need_frontmatter():
    # Arrange
    text = "no frontmatter here\n"

    # Act
    result = lint.yaml_findings(text)

    # Assert
    assert result == []


def test_an_unreadable_skill_file_is_an_io_error(tmp_path):
    # Arrange
    folder = tmp_path / "SKILL.md"
    folder.mkdir()

    # Act
    report = lint.lint_file(folder)

    # Assert
    assert [finding.code for finding in report.findings] == ["io-error"]


def test_discover_skills_resolves_relative_and_skips_missing_targets(tmp_path):
    # Arrange
    targets = ["skills/plan", str(tmp_path / "missing")]

    # Act
    result = lint.discover_skills(targets)

    # Assert
    assert result == [lint.ROOT / "skills" / "plan" / "SKILL.md"]


@pytest.mark.parametrize(
    ("errors", "warnings", "strict", "expected"),
    [(1, 0, False, 1), (0, 1, True, 1), (0, 1, False, 0), (0, 0, True, 0)],
)
def test_exit_code_counts_warnings_only_in_strict_mode(
    errors, warnings, strict, expected
):
    # Arrange
    counts = (errors, warnings, strict)

    # Act
    result = lint.exit_code(*counts)

    # Assert
    assert result == expected


def test_the_json_report_runs_end_to_end():
    # Arrange
    args = ["--json", str(Path(lint.ROOT) / "skills" / "plan")]

    # Act
    proc = run_linter(args)

    # Assert
    assert proc.returncode == 0
    assert proc.stdout.lstrip().startswith("{")
