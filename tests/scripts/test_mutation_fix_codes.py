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
