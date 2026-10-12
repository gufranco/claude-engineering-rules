from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.comment_families import verbatim  # noqa: E402
from _lib.comment_family_index import (  # noqa: E402
    BASENAME_FAMILIES,
    EXTENSION_FAMILIES,
)
from _lib.tool_directive import TOOL_DIRECTIVE  # noqa: E402


def test_keys_every_extension_with_a_lowercase_dot() -> None:
    # Arrange
    keys = list(EXTENSION_FAMILIES)

    # Act
    malformed = [key for key in keys if not key.startswith(".") or key != key.lower()]

    # Assert
    assert malformed == []


def test_keys_every_basename_in_lowercase() -> None:
    # Arrange
    keys = list(BASENAME_FAMILIES)

    # Act
    malformed = [key for key in keys if key != key.lower()]

    # Assert
    assert malformed == []


@pytest.mark.parametrize(
    "body",
    ["# LANGUAGE OverloadedStrings #", "# INLINE f #", "v7.0.1", "4.37.8", "v2"],
)
def test_matches_a_pragma_or_version_pin(body: str) -> None:
    # Arrange
    candidate = body

    # Act
    match = TOOL_DIRECTIVE.match(candidate)

    # Assert
    assert match is not None


@pytest.mark.parametrize(
    "body",
    [
        "# Warning: be careful",
        "# language matters",
        "the eslint rule is wrong",
        "vi: remember this",
        "version 7 is pinned",
    ],
)
def test_rejects_prose_that_resembles_a_directive(body: str) -> None:
    # Arrange
    candidate = body

    # Act
    match = TOOL_DIRECTIVE.match(candidate)

    # Assert
    assert match is None


def test_builds_a_verbatim_multiline_string_token() -> None:
    # Arrange
    quote = "'"

    # Act
    token = verbatim(quote, multiline=True)

    # Assert
    assert (token.escape, token.line_terminated) == ("", False)
