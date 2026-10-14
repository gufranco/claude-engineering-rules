from __future__ import annotations


import pytest

from _helpers.markdown_link_detector_support import (
    Finding,
    GENERIC_FILENAME_TOKENS,
    REPO_ROOT,
    column_inside_ranges,
    detect_findings,
    find_code_block_ranges,
    find_link_url_ranges,
    is_already_linked,
    is_file_path_token,
    line_is_inside_ranges,
    resolve_path,
)


@pytest.mark.parametrize("token", ["README.md", "hooks/_lib/validate.py", "foo/bar/"])
def test_is_file_path_token_accepts_extension(token):
    # Arrange
    candidate = token

    # Act
    result = is_file_path_token(candidate)

    # Assert
    assert result is True


@pytest.mark.parametrize("token", [".", "..", "./", "a"])
def test_is_file_path_token_rejects_short_tokens(token):
    # Arrange
    candidate = token

    # Act
    result = is_file_path_token(candidate)

    # Assert
    assert result is False


def test_is_file_path_token_rejects_command_with_space():
    # Arrange
    candidate = "git status"

    # Act
    result = is_file_path_token(candidate)

    # Assert
    assert result is False


def test_is_file_path_token_rejects_option_flag():
    # Arrange
    candidate = "--force"

    # Act
    result = is_file_path_token(candidate)

    # Assert
    assert result is False


@pytest.mark.parametrize("token", ["https://example.com/foo.md", "mailto:a@b.com"])
def test_is_file_path_token_rejects_urls(token):
    # Arrange
    candidate = token

    # Act
    result = is_file_path_token(candidate)

    # Assert
    assert result is False


@pytest.mark.parametrize("token", [".git", "node_modules/"])
def test_is_file_path_token_rejects_vcs_metadata(token):
    # Arrange
    candidate = token

    # Act
    result = is_file_path_token(candidate)

    # Assert
    assert result is False


@pytest.mark.parametrize("token", ["README", "hello"])
def test_is_file_path_token_rejects_plain_words(token):
    # Arrange
    candidate = token

    # Act
    result = is_file_path_token(candidate)

    # Assert
    assert result is False


def test_find_code_block_ranges_simple():
    # Arrange
    text = "before\n```\ninside\n```\nafter"

    # Act
    ranges = find_code_block_ranges(text)

    # Assert
    assert ranges == [(2, 4)]


def test_find_code_block_ranges_unclosed():
    # Arrange
    text = "before\n```\nstill in block"

    # Act
    ranges = find_code_block_ranges(text)

    # Assert
    assert ranges == [(2, 3)]


def test_find_code_block_ranges_front_matter():
    # Arrange
    text = "---\nfront-matter\n---\nbody"

    # Act
    ranges = find_code_block_ranges(text)

    # Assert
    assert ranges == [(1, 3)]


@pytest.mark.parametrize(
    ("line", "expected"), [(1, False), (2, True), (5, True), (6, False)]
)
def test_line_is_inside_ranges(line, expected):
    # Arrange
    ranges = [(2, 5)]

    # Act
    result = line_is_inside_ranges(line, ranges)

    # Assert
    assert result is expected


def test_find_link_url_ranges():
    # Arrange
    line = "See [`README.md`](README.md) for details."

    # Act
    ranges = find_link_url_ranges(line)

    # Assert
    assert ranges == [(18, 27)]


@pytest.mark.parametrize(("column", "expected"), [(7, True), (11, False)])
def test_column_inside_ranges(column, expected):
    # Arrange
    ranges = [(5, 10)]

    # Act
    result = column_inside_ranges(column, ranges)

    # Assert
    assert result is expected


def test_is_already_linked_backticks_inside_link_text():
    # Arrange
    line = "See [`README.md`](README.md) details"
    span_start = line.find("`")
    span_end = line.find("`", span_start + 1) + 1

    # Act
    linked = is_already_linked(line, span_start, span_end)

    # Assert
    assert linked is True


def test_is_already_linked_not_in_link():
    # Arrange
    line = "Plain `README.md` mention"
    span_start = line.find("`")
    span_end = line.find("`", span_start + 1) + 1

    # Act
    linked = is_already_linked(line, span_start, span_end)

    # Assert
    assert linked is False


def test_resolve_path_existing_relative():
    # Arrange
    doc_dir = REPO_ROOT

    # Act
    resolved = resolve_path("README.md", doc_dir, REPO_ROOT)

    # Assert
    assert resolved == REPO_ROOT / "README.md"


def test_resolve_path_non_existing():
    # Arrange
    doc_dir = REPO_ROOT

    # Act
    resolved = resolve_path("nowhere/foo.md", doc_dir, REPO_ROOT)

    # Assert
    assert resolved is None


def test_resolve_path_absolute_rejected():
    # Arrange
    doc_dir = REPO_ROOT

    # Act
    resolved = resolve_path("/etc/passwd", doc_dir, REPO_ROOT)

    # Assert
    assert resolved is None


def test_detect_findings_clean_text():
    # Arrange
    text = "# Clean\n\nSee [`README.md`](README.md) here.\n"

    # Act
    findings = detect_findings(text, "tmp.md", REPO_ROOT)

    # Assert
    assert findings == []


def test_detect_findings_bare_reference():
    # Arrange
    text = "Look at `README.md` directly.\n"

    # Act
    findings = detect_findings(text, "tmp.md", REPO_ROOT)

    # Assert
    assert findings == [Finding("tmp.md", 1, 9, "README.md", "README.md")]


def test_detect_findings_skips_fenced_block():
    # Arrange
    text = "```\nbare `README.md` inside code block\n```\n"

    # Act
    findings = detect_findings(text, "tmp.md", REPO_ROOT)

    # Assert
    assert findings == []


def test_detect_findings_skips_generic_config_filename():
    # Arrange
    text = "Detect the package manager from `package.json`.\n"

    # Act
    findings = detect_findings(text, "tmp.md", REPO_ROOT)

    # Assert
    assert findings == []


@pytest.mark.parametrize("token", sorted(GENERIC_FILENAME_TOKENS))
def test_detect_findings_skips_every_generic_filename_token(token):
    # Arrange
    text = f"Read `{token}` in the target project.\n"

    # Act
    findings = detect_findings(text, "tmp.md", REPO_ROOT)

    # Assert
    assert findings == []


def test_detect_findings_still_flags_repo_owned_path():
    # Arrange
    text = "Look at `rules/markdown-links.md` directly.\n"

    # Act
    findings = detect_findings(text, "tmp.md", REPO_ROOT)

    # Assert
    assert findings == [
        Finding("tmp.md", 1, 9, "rules/markdown-links.md", "rules/markdown-links.md")
    ]


def test_detect_findings_skips_skip_dir():
    # Arrange
    text = "Look at `README.md` directly.\n"

    # Act
    findings = detect_findings(text, "tests/foo.md", REPO_ROOT)

    # Assert
    assert findings == []


def test_detect_findings_skips_exempt_file():
    # Arrange
    text = "Look at `README.md` directly.\n"

    # Act
    findings = detect_findings(text, "rules/markdown-links.md", REPO_ROOT)

    # Assert
    assert findings == []
