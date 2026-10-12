from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import mutation_detectors_methods as mdm  # noqa: E402


def test_array_pop_skips_web_api_owner() -> None:
    # Arrange
    text = "const params: URLSearchParams = new URLSearchParams();\nparams.pop();\n"

    # Act
    hits = mdm.detect_array_pop_shift_unshift_splice_reverse_fill_copywithin(
        text, "ts", "src/foo.ts"
    )

    # Assert
    assert hits == []


def test_array_push_skips_web_api_owner() -> None:
    # Arrange
    text = (
        "const params: URLSearchParams = new URLSearchParams();\n"
        "params.push(['x', '1']);\n"
    )

    # Act
    hits = mdm.detect_array_push(text, "ts", "src/foo.ts")

    # Assert
    assert hits == []


def test_map_set_skips_temporal_chain() -> None:
    # Arrange
    text = "const t = Temporal.Now.instant();\nconst tomorrow = t.set({ hours: 24 });\n"

    # Act
    hits = mdm.detect_map_set_collection_mutations(text, "ts", "src/foo.ts")

    # Assert
    assert hits == []


def test_map_set_skips_web_api_owner() -> None:
    # Arrange
    text = (
        "const m = new Map();\n"
        "const headers: Headers = new Headers();\n"
        "headers.set('content-type', 'application/json');\n"
    )

    # Act
    hits = mdm.detect_map_set_collection_mutations(text, "ts", "src/foo.ts")

    # Assert
    assert all("headers" not in h.metadata.get("kind", "") for h in hits)


def test_map_delete_skips_web_api_owner() -> None:
    # Arrange
    text = (
        "const m = new Map();\n"
        "const headers: Headers = new Headers();\n"
        "headers.delete('content-type');\n"
    )

    # Act
    hits = mdm.detect_map_set_collection_mutations(text, "ts", "src/foo.ts")

    # Assert
    detectors = [h.detector for h in hits]
    assert "collection.map.delete" not in detectors


def test_map_delete_skips_temporal_chain() -> None:
    # Arrange
    text = (
        "const m = new Map();\n"
        "const t = Temporal.Now.instant();\n"
        "const next = t.delete({ hours: 1 });\n"
    )

    # Act
    hits = mdm.detect_map_set_collection_mutations(text, "ts", "src/foo.ts")

    # Assert
    detectors = [h.detector for h in hits]
    assert "collection.map.delete" not in detectors


def test_map_clear_skips_web_api_owner() -> None:
    # Arrange
    text = (
        "const m: Map<string, number> = new Map();\n"
        "const headers: Headers = new Headers();\n"
        "headers.clear();\n"
    )

    # Act
    hits = mdm.detect_map_set_collection_mutations(text, "ts", "src/foo.ts")

    # Assert
    detectors = [h.detector for h in hits]
    assert "collection.map.clear" not in detectors


def test_set_add_skips_web_api_owner() -> None:
    # Arrange
    text = (
        "const s = new Set();\n"
        "const fd: FormData = new FormData();\n"
        "fd.add('field', 'value');\n"
    )

    # Act
    hits = mdm.detect_map_set_collection_mutations(text, "ts", "src/foo.ts")

    # Assert
    detectors = [h.detector for h in hits]
    assert "collection.set.add" not in detectors


def test_set_delete_skips_temporal_chain() -> None:
    # Arrange
    text = (
        "const s = new Set();\n"
        "const t = Temporal.Now.instant();\n"
        "const next = t.delete({ hours: 1 });\n"
    )

    # Act
    hits = mdm.detect_map_set_collection_mutations(text, "ts", "src/foo.ts")

    # Assert
    detectors = [h.detector for h in hits]
    assert "collection.set.delete" not in detectors


def test_url_search_params_skips_unanchored_owner() -> None:
    # Arrange
    text = "const params = new URLSearchParams();\nother.append('x', 'y');\n"

    # Act
    hits = mdm.detect_url_search_params_mutations(text, "ts", "src/foo.ts")

    # Assert
    detectors = [h.detector for h in hits]
    assert all(d != "web-api.url-search-params.append" for d in detectors)


def test_headers_skips_when_no_strong_signal() -> None:
    # Arrange
    text = "// Headers helpers\nheadersBag.append('x', 'y');\n"

    # Act
    hits = mdm.detect_headers_mutations(text, "ts", "src/foo.ts")

    # Assert
    assert hits == []
