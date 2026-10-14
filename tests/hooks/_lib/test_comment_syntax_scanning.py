from __future__ import annotations


from _helpers.comment_syntax_support import (
    added_comment_lines,
    comment_lines,
    family_for,
    mask_code,
    reported_numbers,
    scan_hits,
)


def test_reports_a_block_comment_marker() -> None:
    # Arrange
    family = family_for("src/a.test.ts")

    # Act
    pairs = comment_lines("/* Arrange */\nconst x = 1\n", family, allow_aaa=True)

    # Assert
    assert reported_numbers(pairs) == (1,)


def test_reports_a_bare_marker_outside_a_test_file() -> None:
    # Arrange
    family = family_for("src/app.py")

    # Act
    pairs = comment_lines("# Arrange\nx = 1\n", family)

    # Assert
    assert reported_numbers(pairs) == (1,)


def test_reports_only_the_docstring_an_edit_adds() -> None:
    # Arrange
    family = family_for("src/app.py")
    before = 'def f():\n    """Old."""\n    return 1\n\n\ndef g():\n    return 2\n'
    after = before.replace("    return 2\n", '    """New."""\n    return 2\n')

    # Act
    pairs = added_comment_lines(before, after, family)

    # Assert
    assert pairs == [(6, '"""New."""')]


def test_ignores_a_docstring_that_already_existed() -> None:
    # Arrange
    family = family_for("src/app.py")
    before = '"""Module."""\n\nx = 1\n'
    after = '"""Module."""\n\nx = 2\n'

    # Act
    pairs = added_comment_lines(before, after, family)

    # Assert
    assert pairs == []


def test_reports_a_string_statement_that_is_not_a_docstring_as_nothing() -> None:
    # Arrange
    family = family_for("src/app.py")

    # Act
    pairs = comment_lines('x = 1\n"""Not a docstring."""\n', family)

    # Assert
    assert pairs == []


def test_scans_python_that_does_not_parse() -> None:
    # Arrange
    family = family_for("src/app.py")

    # Act
    pairs = comment_lines("def f(:\n    # note\n", family)

    # Assert
    assert reported_numbers(pairs) == (2,)


def test_reports_a_second_copy_of_an_existing_comment() -> None:
    # Arrange
    family = family_for("src/app.py")

    # Act
    pairs = added_comment_lines("# note\nx = 1\n", "# note\nx = 1\n# note\n", family)

    # Assert
    assert pairs == [(2, "# note")]


def test_marks_a_hit_with_its_token_and_position() -> None:
    # Arrange
    family = family_for("src/a.ts")

    # Act
    hits = scan_hits("const a = 1 // tail\n// whole\n/* x\n y */\n", family)

    # Assert
    assert [
        (line, hit.token, hit.whole_line, hit.body) for line, hit in hits.items()
    ] == [
        (0, "//", False, "tail"),
        (1, "//", True, "whole"),
        (2, "/*", True, "x"),
        (3, "", False, None),
    ]


def test_masks_strings_and_comments_preserving_length_and_lines() -> None:
    # Arrange
    family = family_for("src/a.ts")
    text = 'const s = "{x}" // {y}\nconst t = 1\n'

    # Act
    masked = mask_code(text, family)

    # Assert
    assert masked == 'const s = "   "       \nconst t = 1\n'


def test_masks_a_region_family_document() -> None:
    # Arrange
    family = family_for("web/a.html")
    text = "<script>\nconst s = '}'\n</script>\n"

    # Act
    masked = mask_code(text, family)

    # Assert
    assert masked == "<script>\nconst s = ' '\n</script>\n"


def test_ignores_a_shebang_on_the_first_line() -> None:
    # Arrange
    family = family_for("scripts/run.sh")

    # Act
    pairs = comment_lines("#!/usr/bin/env bash\necho hi\n", family)

    # Assert
    assert pairs == []


def test_leaves_an_unterminated_block_comment_reported_to_the_end() -> None:
    # Arrange
    family = family_for("src/A.hs")

    # Act
    pairs = comment_lines("{- open\n{- nested\nx = 1\n", family)

    # Assert
    assert reported_numbers(pairs) == (1, 2, 3)


def test_ignores_a_heredoc_whose_terminator_never_appears() -> None:
    # Arrange
    family = family_for("scripts/a.sh")

    # Act
    pairs = comment_lines("cat <<EOF\n# real comment\n", family)

    # Assert
    assert reported_numbers(pairs) == (2,)
