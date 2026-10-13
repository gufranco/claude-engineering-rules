from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.mutation_detectors_methods import (  # noqa: E402
    detect_map_set_collection_mutations,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "const seen = new Set<string>();\n"
            "const ids = rows.map((row) => row.id);\n"
            "seen.add(ids[0]);\n",
            ["collection.set.add"],
        ),
        (
            "const tags = new Set<string>();\n"
            "const cache = new Map<string, number>();\n"
            "cache.set('a', 1);\n"
            "tags.add('a');\n"
            "tags.delete('a');\n",
            ["collection.map.set", "collection.set.add", "collection.set.delete"],
        ),
        (
            "const cache = new Map<string, number>();\n"
            "const tags = new Set<string>();\n"
            "cache.delete('a');\n",
            ["collection.map.delete"],
        ),
    ],
    ids=["map-call-in-window", "both-kinds-declared", "map-delete-beside-set"],
)
def test_each_receiver_is_classified_by_its_own_declaration(text, expected):
    # Arrange
    source = text

    # Act
    matches = detect_map_set_collection_mutations(source, "ts", "src/module.ts")

    # Assert
    assert [m.detector for m in matches] == expected
