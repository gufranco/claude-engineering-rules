from __future__ import annotations

import json
from pathlib import Path

SUGGESTIONS = (
    Path(__file__).resolve().parents[2] / "hooks" / "mutation_fix_suggestions.json"
)


def test_each_category_code_belongs_to_an_exact_entry_of_that_category():
    # Arrange
    data = json.loads(SUGGESTIONS.read_text(encoding="utf-8"))
    owners = {entry["code"]: entry.get("category") for entry in data["exact"].values()}

    # Act
    mismatched = {
        name: owners.get(entry["code"])
        for name, entry in data["by_category"].items()
        if entry.get("code") in owners and owners[entry["code"]] != name
    }

    # Assert
    assert mismatched == {}


def test_exact_entries_have_unique_codes() -> None:
    # Arrange
    data = json.loads(SUGGESTIONS.read_text(encoding="utf-8"))

    # Act
    codes = [entry["code"] for entry in data["exact"].values()]

    # Assert
    assert len(codes) == len(set(codes))


def test_every_exact_entry_has_code_category_and_fix() -> None:
    # Arrange
    data = json.loads(SUGGESTIONS.read_text(encoding="utf-8"))

    # Act
    malformed = [
        tag
        for tag, entry in data["exact"].items()
        if not (
            entry.get("code", "").startswith("MMB")
            and "category" in entry
            and len(entry.get("fix", "")) > 20
        )
    ]

    # Assert
    assert malformed == []
