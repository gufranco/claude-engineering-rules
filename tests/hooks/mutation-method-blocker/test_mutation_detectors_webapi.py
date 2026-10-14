from __future__ import annotations

import sys
from pathlib import Path

from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_detectors_webapi import (  # noqa: E402
    detect_form_data_mutations,
    detect_headers_mutations,
    detect_url_search_params_mutations,
)


def _source(faker: Faker) -> str:
    return f"/repo/src/{faker.word()}.ts"


def test_url_search_params_flags_a_constructed_receiver(faker: Faker) -> None:
    # Arrange
    text = "const params = new URLSearchParams();\nparams.append('a', '1');\n"

    # Act
    hits = detect_url_search_params_mutations(text, "ts", _source(faker))

    # Assert
    assert [(h.detector, h.line, h.metadata["confidence"]) for h in hits] == [
        ("web-api.url-search-params.append", 2, "5")
    ]


def test_url_search_params_ignores_text_without_any_signal(faker: Faker) -> None:
    # Arrange
    text = "cache.set('a', 1);\n"

    # Act
    hits = detect_url_search_params_mutations(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_headers_skips_a_fresh_reducer_accumulator(faker: Faker) -> None:
    # Arrange
    text = "const out = list.reduce((acc, [k, v]) => { acc.set(k, v); return acc; }, new Headers());\n"

    # Act
    hits = detect_headers_mutations(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_headers_flags_only_the_anchored_receiver(faker: Faker) -> None:
    # Arrange
    text = "function f(h: Headers) {\n  h.delete('x');\n  other.delete('y');\n}\n"

    # Act
    hits = detect_headers_mutations(text, "ts", _source(faker))

    # Assert
    assert [(h.detector, h.metadata["owner"]) for h in hits] == [
        ("web-api.headers.delete", "h")
    ]


def test_form_data_name_hint_alone_is_not_a_strong_signal(faker: Faker) -> None:
    # Arrange
    text = "userFormData.append('a', 1);\n"

    # Act
    hits = detect_form_data_mutations(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_form_data_flags_with_a_low_confidence(faker: Faker) -> None:
    # Arrange
    text = "const fd = new FormData();\nfd.set('a', 1);\n"

    # Act
    hits = detect_form_data_mutations(text, "ts", _source(faker))

    # Assert
    assert [(h.detector, h.metadata["confidence"]) for h in hits] == [
        ("web-api.form-data.set", "3")
    ]
