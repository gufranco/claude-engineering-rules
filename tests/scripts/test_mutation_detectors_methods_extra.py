"""Extra coverage for `scripts/mutation_detectors_methods.py`.

Targets the Web-API and Temporal dedup branches inside the array,
collection, and Web-API detectors that are not exercised by
`tests/hooks/.../test_*.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import mutation_detectors_methods as mdm  # noqa: E402


# --------------------------------------------------------------------------- #
# detect_array_pop_shift_unshift_splice_reverse_fill_copywithin (line 245)
# --------------------------------------------------------------------------- #


def test_array_pop_skips_web_api_owner() -> None:
    # on URLSearchParams, but the dedup short-circuits before emit.
    text = "const params: URLSearchParams = new URLSearchParams();\nparams.pop();\n"

    hits = mdm.detect_array_pop_shift_unshift_splice_reverse_fill_copywithin(
        text, "ts", "src/foo.ts"
    )

    assert hits == []


# --------------------------------------------------------------------------- #
# detect_array_push (line 279)
# --------------------------------------------------------------------------- #


def test_array_push_skips_web_api_owner() -> None:
    text = (
        "const params: URLSearchParams = new URLSearchParams();\n"
        "params.push(['x', '1']);\n"
    )

    hits = mdm.detect_array_push(text, "ts", "src/foo.ts")

    assert hits == []


# --------------------------------------------------------------------------- #
# Map collection: temporal + web-api dedup (lines 428, 430, 444, 446, 461)
# --------------------------------------------------------------------------- #


def test_map_set_skips_temporal_chain() -> None:
    # short-circuits before emitting a Map.set hit.
    text = "const t = Temporal.Now.instant();\nconst tomorrow = t.set({ hours: 24 });\n"

    hits = mdm.detect_map_set_collection_mutations(text, "ts", "src/foo.ts")

    assert hits == []


def test_map_set_skips_web_api_owner() -> None:
    # detector engages, but the receiver is also a typed Headers instance.
    # Headers.set is a real Web API mutation, but the Map detector should
    # skip it via the web-api dedup.
    text = (
        "const m = new Map();\n"
        "const headers: Headers = new Headers();\n"
        "headers.set('content-type', 'application/json');\n"
    )

    hits = mdm.detect_map_set_collection_mutations(text, "ts", "src/foo.ts")

    assert all("headers" not in h.metadata.get("kind", "") for h in hits)


def test_map_delete_skips_web_api_owner() -> None:
    text = (
        "const m = new Map();\n"
        "const headers: Headers = new Headers();\n"
        "headers.delete('content-type');\n"
    )

    hits = mdm.detect_map_set_collection_mutations(text, "ts", "src/foo.ts")

    detectors = [h.detector for h in hits]
    assert "collection.map.delete" not in detectors


def test_map_delete_skips_temporal_chain() -> None:
    text = (
        "const m = new Map();\n"
        "const t = Temporal.Now.instant();\n"
        "const next = t.delete({ hours: 1 });\n"
    )

    hits = mdm.detect_map_set_collection_mutations(text, "ts", "src/foo.ts")

    detectors = [h.detector for h in hits]
    assert "collection.map.delete" not in detectors


def test_map_clear_skips_web_api_owner() -> None:
    # Headers receiver whose `.clear()` (does not exist on Headers but is
    # syntactically valid) must be deduped.
    text = (
        "const m: Map<string, number> = new Map();\n"
        "const headers: Headers = new Headers();\n"
        "headers.clear();\n"
    )

    hits = mdm.detect_map_set_collection_mutations(text, "ts", "src/foo.ts")

    detectors = [h.detector for h in hits]
    assert "collection.map.clear" not in detectors


# --------------------------------------------------------------------------- #
# Set collection: temporal + web-api dedup (lines 504, 518)
# --------------------------------------------------------------------------- #


def test_set_add_skips_web_api_owner() -> None:
    text = (
        "const s = new Set();\n"
        "const fd: FormData = new FormData();\n"
        "fd.add('field', 'value');\n"
    )

    hits = mdm.detect_map_set_collection_mutations(text, "ts", "src/foo.ts")

    detectors = [h.detector for h in hits]
    assert "collection.set.add" not in detectors


def test_set_delete_skips_temporal_chain() -> None:
    text = (
        "const s = new Set();\n"
        "const t = Temporal.Now.instant();\n"
        "const next = t.delete({ hours: 1 });\n"
    )

    hits = mdm.detect_map_set_collection_mutations(text, "ts", "src/foo.ts")

    detectors = [h.detector for h in hits]
    assert "collection.set.delete" not in detectors


# --------------------------------------------------------------------------- #
# _detect_web_api_collection: anchored vs strong signal (lines 709, 711)
# --------------------------------------------------------------------------- #


def test_url_search_params_skips_unanchored_owner() -> None:
    # engages, but the method call is on a different receiver name.
    text = "const params = new URLSearchParams();\nother.append('x', 'y');\n"

    hits = mdm.detect_url_search_params_mutations(text, "ts", "src/foo.ts")

    detectors = [h.detector for h in hits]
    assert all(d != "web-api.url-search-params.append" for d in detectors)


def test_headers_skips_when_no_strong_signal() -> None:
    # `new Headers()` declaration and no typed annotation.
    text = "// Headers helpers\nheadersBag.append('x', 'y');\n"

    hits = mdm.detect_headers_mutations(text, "ts", "src/foo.ts")

    assert hits == []
