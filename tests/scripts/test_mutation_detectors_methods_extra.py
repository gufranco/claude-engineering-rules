from __future__ import annotations

import sys
from pathlib import Path

from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import mutation_detectors_methods as mdm  # noqa: E402
from _lib import mutation_detectors_webapi as mdw  # noqa: E402


def _source_path(faker: Faker) -> str:
    return f"src/{faker.word()}.ts"


def test_array_pop_skips_web_api_owner(faker: Faker) -> None:
    # Arrange
    text = "const params: URLSearchParams = new URLSearchParams();\nparams.pop();\n"

    # Act
    hits = mdm.detect_array_pop_shift_unshift_splice_reverse_fill_copywithin(
        text, "ts", _source_path(faker)
    )

    # Assert
    assert hits == []


def test_array_push_skips_web_api_owner(faker: Faker) -> None:
    # Arrange
    text = (
        "const params: URLSearchParams = new URLSearchParams();\n"
        f"params.push(['{faker.word()}', '{faker.word()}']);\n"
    )

    # Act
    hits = mdm.detect_array_push(text, "ts", _source_path(faker))

    # Assert
    assert hits == []


def test_map_set_skips_temporal_chain(faker: Faker) -> None:
    # Arrange
    text = "const t = Temporal.Now.instant();\nconst tomorrow = t.set({ hours: 24 });\n"

    # Act
    hits = mdm.detect_map_set_collection_mutations(text, "ts", _source_path(faker))

    # Assert
    assert hits == []


def test_map_set_skips_web_api_owner(faker: Faker) -> None:
    # Arrange
    text = (
        "const m = new Map();\n"
        "const headers: Headers = new Headers();\n"
        f"headers.set('{faker.word()}', '{faker.word()}');\n"
    )

    # Act
    hits = mdm.detect_map_set_collection_mutations(text, "ts", _source_path(faker))

    # Assert
    assert hits == []


def test_map_set_on_a_plain_map_is_flagged(faker: Faker) -> None:
    # Arrange
    text = f"const m = new Map();\nm.set('{faker.word()}', 1);\n"

    # Act
    hits = mdm.detect_map_set_collection_mutations(text, "ts", _source_path(faker))

    # Assert
    assert [(hit.detector, hit.line) for hit in hits] == [("collection.map.set", 2)]


def test_map_delete_skips_web_api_owner(faker: Faker) -> None:
    # Arrange
    text = (
        "const m = new Map();\n"
        "const headers: Headers = new Headers();\n"
        f"headers.delete('{faker.word()}');\n"
    )

    # Act
    hits = mdm.detect_map_set_collection_mutations(text, "ts", _source_path(faker))

    # Assert
    assert hits == []


def test_map_delete_skips_temporal_chain(faker: Faker) -> None:
    # Arrange
    text = (
        "const m = new Map();\n"
        "const t = Temporal.Now.instant();\n"
        "const next = t.delete({ hours: 1 });\n"
    )

    # Act
    hits = mdm.detect_map_set_collection_mutations(text, "ts", _source_path(faker))

    # Assert
    assert hits == []


def test_map_clear_skips_web_api_owner(faker: Faker) -> None:
    # Arrange
    text = (
        "const m: Map<string, number> = new Map();\n"
        "const headers: Headers = new Headers();\n"
        "headers.clear();\n"
    )

    # Act
    hits = mdm.detect_map_set_collection_mutations(text, "ts", _source_path(faker))

    # Assert
    assert hits == []


def test_set_add_skips_web_api_owner(faker: Faker) -> None:
    # Arrange
    text = (
        "const s = new Set();\n"
        "const fd: FormData = new FormData();\n"
        f"fd.add('{faker.word()}', '{faker.word()}');\n"
    )

    # Act
    hits = mdm.detect_map_set_collection_mutations(text, "ts", _source_path(faker))

    # Assert
    assert hits == []


def test_set_delete_skips_temporal_chain(faker: Faker) -> None:
    # Arrange
    text = (
        "const s = new Set();\n"
        "const t = Temporal.Now.instant();\n"
        "const next = t.delete({ hours: 1 });\n"
    )

    # Act
    hits = mdm.detect_map_set_collection_mutations(text, "ts", _source_path(faker))

    # Assert
    assert hits == []


def test_url_search_params_skips_unanchored_owner(faker: Faker) -> None:
    # Arrange
    text = (
        "const params = new URLSearchParams();\n"
        f"other.append('{faker.word()}', '{faker.word()}');\n"
    )

    # Act
    hits = mdw.detect_url_search_params_mutations(text, "ts", _source_path(faker))

    # Assert
    assert hits == []


def test_url_search_params_flags_the_anchored_owner(faker: Faker) -> None:
    # Arrange
    text = (
        "const params = new URLSearchParams();\n"
        f"params.append('{faker.word()}', '{faker.word()}');\n"
    )

    # Act
    hits = mdw.detect_url_search_params_mutations(text, "ts", _source_path(faker))

    # Assert
    assert [(hit.detector, hit.line) for hit in hits] == [
        ("web-api.url-search-params.append", 2)
    ]


def test_headers_skips_when_no_strong_signal(faker: Faker) -> None:
    # Arrange
    text = (
        f"// Headers helpers\nheadersBag.append('{faker.word()}', '{faker.word()}');\n"
    )

    # Act
    hits = mdw.detect_headers_mutations(text, "ts", _source_path(faker))

    # Assert
    assert hits == []
