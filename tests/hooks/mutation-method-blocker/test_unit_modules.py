from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "hooks"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import mutation_detectors_assignments as assignments  # noqa: E402
from _lib import mutation_detectors_core as core  # noqa: E402


def test_detect_lang_empty_path():
    # Arrange
    path = ""

    # Act
    result = core.detect_lang(path)

    # Assert
    assert result is None


def test_detect_lang_unknown_extension():
    # Arrange
    path = "/repo/src/app.rs"

    # Act
    result = core.detect_lang(path)

    # Assert
    assert result is None


def test_detect_lang_tsx():
    # Arrange
    path = "/repo/src/Component.tsx"

    # Act
    result = core.detect_lang(path)

    # Assert
    assert result == "tsx"


def test_detect_lang_mjs_maps_to_js():
    # Arrange
    path = "/repo/src/main.mjs"

    # Act
    result = core.detect_lang(path)

    # Assert
    assert result == "js"


def test_supports_ast_none():
    # Arrange
    lang = None

    # Act
    result = core.supports_ast(lang)

    # Assert
    assert result is False


def test_supports_ast_unsupported():
    # Arrange
    lang = "rust"

    # Act
    result = core.supports_ast(lang)

    # Assert
    assert result is False


def test_supports_ast_tsx_true():
    # Arrange
    lang = "tsx"

    # Act
    result = core.supports_ast(lang)

    # Assert
    assert result is True


MULTILINE_SQL = (
    "export const listTables = () => sql`\n"
    "  JOIN pg_namespace n ON n.oid = c.relnamespace\n"
    "  WHERE n.nspname = 'public'\n"
    "`;\n"
    "order.status = 1;\n"
)


def test_mask_lines_masks_a_template_literal_across_lines():
    # Arrange
    source = MULTILINE_SQL

    # Act
    masked = core.mask_lines(source)

    # Assert
    assert len(masked) == len(MULTILINE_SQL.splitlines())
    assert "nspname" not in masked[2]
    assert "relnamespace" not in masked[1]
    assert masked[4] == "order.status = 1;"


def test_mask_lines_masks_a_block_comment_across_lines():
    # Arrange
    text = "a /* one\ntwo.x = 3 */ b.y = 4;"

    # Act
    masked = core.mask_lines(text)

    # Assert
    assert "two" not in masked[1]
    assert masked[1].endswith("b.y = 4;") is True


def test_mask_lines_keeps_an_escaped_backtick_inside_the_literal():
    # Arrange
    text = "const s = `a\\`b.c = 1\n`;\nobj.prop = 1;"

    # Act
    masked = core.mask_lines(text)

    # Assert
    assert "b.c" not in masked[0]
    assert masked[2] == "obj.prop = 1;"


def test_mask_lines_ends_a_quoted_string_at_the_line_break():
    # Arrange
    text = "const s = 'open\nobj.prop = 1;"

    # Act
    masked = core.mask_lines(text)

    # Assert
    assert masked[1] == "obj.prop = 1;"


def test_mask_lines_blanks_string_template_and_comment_on_one_line():
    # Arrange
    line = 'const s = "a\\"b" + `x${y}z`; // tail'
    expected = ['const s = "    " + `      `;        ']

    # Act
    masked = core.mask_lines(line)

    # Assert
    assert masked == expected


def test_sql_in_a_multiline_template_literal_is_not_a_property_assignment():
    # Arrange
    lang = "typescript"

    # Act
    found = assignments.detect_property_assignment(MULTILINE_SQL, lang, "x.ts")

    # Assert
    assert [(match.line, match.text) for match in found] == [(5, "order.status = 1;")]


def test_strip_strings_comments_empty():
    # Arrange
    line = ""

    # Act
    result = core.strip_strings_comments(line)

    # Assert
    assert result == ""


def test_strip_strings_comments_unclosed_block_comment():
    # Arrange
    line = "code /* unclosed comment continues forever"

    # Act
    result = core.strip_strings_comments(line)

    # Assert
    assert result.startswith("code ") is True
    assert "unclosed" not in result


def test_strip_strings_comments_backslash_escape():
    # Arrange
    line = 'const s = "a\\"b\\"c";'

    # Act
    result = core.strip_strings_comments(line)

    # Assert
    assert "a" not in result.split('"')[1]
    assert len(result) == len(line)


def test_strip_strings_comments_template_literal_interpolation():
    # Arrange
    line = "const s = `value=${user.name}`;"

    # Act
    result = core.strip_strings_comments(line)

    # Assert
    assert len(result) == len(line)
    assert "${user.name}" not in result


def test_strip_strings_comments_template_with_nested_braces():
    # Arrange
    line = "const s = `a${{x: 1}.x}b`;"

    # Act
    result = core.strip_strings_comments(line)

    # Assert
    assert len(result) == len(line)


def test_strip_strings_comments_block_comment_closed():
    # Arrange
    line = "code /* inner */ tail"

    # Act
    result = core.strip_strings_comments(line)

    # Assert
    assert "inner" not in result
    assert result.endswith("tail") is True


def test_strip_strings_comments_line_comment():
    # Arrange
    line = "code // tail comment"

    # Act
    result = core.strip_strings_comments(line)

    # Assert
    assert "tail" not in result


def test_window_around_empty_lines():
    # Arrange
    lines: list[str] = []

    # Act
    result = core.window_around(lines, 5)

    # Assert
    assert result == ""


def test_window_around_clamp_lower():
    # Arrange
    lines = ["a", "b", "c"]

    # Act
    result = core.window_around(lines, 1, before=10, after=0)

    # Assert
    assert result == "a"


def test_window_around_clamp_upper():
    # Arrange
    lines = ["a", "b", "c"]

    # Act
    result = core.window_around(lines, 3, before=0, after=10)

    # Assert
    assert result == "c"


def test_truncate_excerpt_short():
    # Arrange
    line = "  short  "

    # Act
    result = core.truncate_excerpt(line, limit=120)

    # Assert
    assert result == "short"


def test_truncate_excerpt_long():
    # Arrange
    line = "x" * 200

    # Act
    result = core.truncate_excerpt(line, limit=10)

    # Assert
    assert result.endswith("...") is True
    assert len(result) <= 13
