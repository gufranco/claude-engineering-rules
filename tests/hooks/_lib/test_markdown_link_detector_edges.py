from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib import markdown_link_detector as detector  # noqa: E402


def test_an_unclosed_frontmatter_block_is_not_a_range():
    # Arrange
    lines = ["---", "title: x", "body"]

    # Act
    result = detector._frontmatter_range(lines)

    # Assert
    assert result == []


@pytest.mark.parametrize(
    ("line", "token", "expected"),
    [
        ("see [the `a.md` file](a.md)", "`a.md`", True),
        ("[`a.md` and more", "`a.md`", False),
        ("plain `a.md` text", "`a.md`", False),
        ("[x](y.md) then [see `b.md` here](b.md)", "`b.md`", True),
    ],
)
def test_is_already_linked_checks_the_surrounding_link(line, token, expected):
    # Arrange
    start = line.index(token)

    # Act
    result = detector.is_already_linked(line, start, start + len(token))

    # Assert
    assert result is expected


def test_a_token_inside_a_link_url_is_not_a_candidate():
    # Arrange
    url_ranges = [(0, 20)]

    # Act
    result = detector._is_candidate_token("a.md", 5, url_ranges)

    # Assert
    assert result is False


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("#section", None),
        ("", None),
        ("https://x.test/a.md", None),
        ("./docs/a.md#part", "docs/a.md"),
        ("/abs/a.md", None),
    ],
)
def test_relative_link_target_keeps_only_repo_relative_paths(url, expected):
    # Arrange
    candidate = url

    # Act
    result = detector._relative_link_target(candidate)

    # Assert
    assert result == expected


def test_a_target_outside_the_repository_gets_no_suggestion(tmp_path):
    # Arrange
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "outside.md").write_text("x", encoding="utf-8")
    context = detector._DocContext("doc.md", repo, repo, None)

    # Act
    result = detector._suggested_path("../outside.md", context)

    # Assert
    assert result is None


def test_a_candidate_outside_the_repository_is_checked_on_disk(tmp_path):
    # Arrange
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("x", encoding="utf-8")

    # Act
    result = detector._target_exists(outside, repo, set())

    # Assert
    assert result is True
