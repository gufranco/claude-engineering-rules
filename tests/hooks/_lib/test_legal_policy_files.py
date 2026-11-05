from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.legal_policy_files import (  # noqa: E402
    ask_decision,
    is_legal_policy_file,
    needs_approval,
)

fake = Faker()
Faker.seed(4204)


def _repo_path(name: str) -> str:
    return str(Path("/", fake.word(), fake.word(), name))


@pytest.mark.parametrize(
    "name",
    [
        "CLEAN_ROOM.md",
        "clean-room.md",
        "CleanRoom.txt",
        "LICENSE",
        "LICENSE.md",
        "licence.txt",
        "COPYING",
        "NOTICE",
        "notice.rst",
        "THIRD_PARTY_NOTICES.md",
        "third-party-notices.txt",
        "LEGAL.md",
    ],
)
def test_recognizes_policy_file_names(name: str) -> None:
    # Arrange
    path = _repo_path(name)

    # Act
    result = is_legal_policy_file(path)

    # Assert
    assert result is True


def test_recognizes_any_file_in_licenses_directory() -> None:
    # Arrange
    path = str(Path("/", fake.word(), "LICENSES", f"{fake.word()}.txt"))

    # Act
    result = is_legal_policy_file(path)

    # Assert
    assert result is True


@pytest.mark.parametrize(
    "name",
    ["license.ts", "notice.py", "legal_terms.md", "README.md", "licenses.json"],
)
def test_ignores_source_files_named_like_policies(name: str) -> None:
    # Arrange
    path = _repo_path(name)

    # Act
    result = is_legal_policy_file(path)

    # Assert
    assert result is False


def test_new_policy_file_needs_no_approval(tmp_path: Path) -> None:
    # Arrange
    path = str(tmp_path / "LICENSE")

    # Act
    result = needs_approval("Write", path)

    # Assert
    assert result is False


def test_overwriting_existing_policy_file_needs_approval(tmp_path: Path) -> None:
    # Arrange
    existing = tmp_path / "NOTICE"
    existing.write_text(fake.sentence(), encoding="utf-8")

    # Act
    result = needs_approval("Write", str(existing))

    # Assert
    assert result is True


def test_editing_policy_file_needs_approval(tmp_path: Path) -> None:
    # Arrange
    path = str(tmp_path / "CLEAN_ROOM.md")

    # Act
    result = needs_approval("Edit", path)

    # Assert
    assert result is True


def test_editing_ordinary_file_needs_no_approval(tmp_path: Path) -> None:
    # Arrange
    path = str(tmp_path / f"{fake.word()}.py")

    # Act
    result = needs_approval("Edit", path)

    # Assert
    assert result is False


def test_ask_decision_names_the_file_and_rule() -> None:
    # Arrange
    path = _repo_path("NOTICE")

    # Act
    decision = json.loads(ask_decision(path))

    # Assert
    output = decision["hookSpecificOutput"]
    assert output["permissionDecision"] == "ask"
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecisionReason"].startswith(
        "NOTICE is a legal policy file"
    )
    assert output["permissionDecisionReason"].endswith("Rule: rules/clean-room.md")
