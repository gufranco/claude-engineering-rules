from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib import mutation_source_map as source_map  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    monkeypatch.setattr(source_map, "_SOURCE_MAP_CACHE", {})


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("", False),
        ("src/app.ts", False),
        ("web/dist/app.js", True),
        ("C:\\proj\\build\\x.js", True),
    ],
)
def test_is_transpiled_path_spots_build_output(path, expected):
    # Arrange
    candidate = path

    # Act
    result = source_map.is_transpiled_path(candidate)

    # Assert
    assert result is expected


@pytest.mark.parametrize(
    ("segment", "expected"),
    [("AAAA", [0, 0, 0, 0]), ("C", [1]), ("D", [-1]), ("gB", [16]), ("A!A", [0])],
)
def test_decode_vlq_reads_base64_digits(segment, expected):
    # Arrange
    text = segment

    # Act
    result = source_map._decode_vlq(text)

    # Assert
    assert result == expected


def test_parse_mappings_accumulates_relative_positions():
    # Arrange
    mappings = "AAAA,CAAC,!,,C;AACA"

    # Act
    result = source_map._parse_mappings(mappings)

    # Assert
    assert result == [[[0, 0, 0, 0], [1, 0, 0, 1], [2]], [[0, 0, 1, 1]]]


def _write_map(tmp_path: Path, payload: object, name: str = "app.js") -> str:
    target = tmp_path / name
    target.write_text("code", encoding="utf-8")
    (tmp_path / f"{name}.map").write_text(json.dumps(payload), encoding="utf-8")
    return str(target)


def test_load_source_map_decodes_and_caches(tmp_path):
    # Arrange
    path = _write_map(
        tmp_path, {"mappings": "AAAA", "sources": ["a.ts"], "sourceRoot": "src"}
    )
    first = source_map.load_source_map(path)
    (tmp_path / "app.js.map").unlink()

    # Act
    result = source_map.load_source_map(path)

    # Assert
    assert result is first
    assert result == {
        "sources": ["a.ts"],
        "sourceRoot": "src",
        "decoded": [[[0, 0, 0, 0]]],
    }


@pytest.mark.parametrize(
    "payload", [["not", "a", "dict"], {"sources": []}, {"mappings": 7}]
)
def test_load_source_map_rejects_unusable_maps(tmp_path, payload):
    # Arrange
    path = _write_map(tmp_path, payload)

    # Act
    result = source_map.load_source_map(path)

    # Assert
    assert result is None


@pytest.mark.parametrize("map_text", [None, "{nope"])
def test_load_source_map_rejects_a_missing_or_broken_file(tmp_path, map_text):
    # Arrange
    target = tmp_path / "b.js"
    target.write_text("code", encoding="utf-8")
    if map_text is not None:
        (tmp_path / "b.js.map").write_text(map_text, encoding="utf-8")

    # Act
    result = source_map.load_source_map(str(target))

    # Assert
    assert result is None


@pytest.mark.parametrize(
    ("line", "col", "expected"),
    [
        (1, 5, ("src/a.ts", 1, 0)),
        (2, 0, ("/abs/b.ts", 3, 2)),
        (0, 0, None),
        (9, 0, None),
        (3, 0, None),
        (4, 0, None),
    ],
)
def test_map_to_original_resolves_positions(line, col, expected):
    # Arrange
    bundle = {
        "sources": ["a.ts", "/abs/b.ts"],
        "sourceRoot": "src/",
        "decoded": [
            [[0, 0, 0, 0], [3]],
            [[0, 1, 2, 2], [9, 1, 2, 2]],
            [[4, 0, 0, 0]],
            [[0, 5, 0, 0]],
        ],
    }

    # Act
    result = source_map.map_to_original(bundle, line, col)

    # Assert
    assert result == expected


def test_map_to_original_without_a_root_keeps_the_relative_source():
    # Arrange
    bundle = {"sources": ["a.ts"], "decoded": [[[0, 0, 0, 0]]]}

    # Act
    result = source_map.map_to_original(bundle, 1, 0)

    # Assert
    assert result == ("a.ts", 1, 0)
