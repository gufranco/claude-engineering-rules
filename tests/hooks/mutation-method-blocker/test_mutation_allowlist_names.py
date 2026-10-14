from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_allowlist_names import (  # noqa: E402
    DOM_PROPERTY_NAMES,
    DOM_RECEIVER_NAMES,
    DOM_TYPED_RECEIVER_PATTERN,
    ES2024_STATIC_NON_MUTATING_FACTORIES,
    PARAM_REASSIGN_ALLOWLIST,
    TEMPORAL_FACTORY_VAR_DECL_PATTERN,
    TEMPORAL_IMMUTABLE_METHODS,
    WEB_API_TYPED_RECEIVER_TYPES,
)


def test_dom_tables_name_the_document_and_inner_html() -> None:
    # Arrange
    receiver, prop = "document", "innerHTML"

    # Act
    found = (receiver in DOM_RECEIVER_NAMES, prop in DOM_PROPERTY_NAMES)

    # Assert
    assert found == (True, True)


def test_dom_typed_receiver_pattern_matches_an_element_suffix() -> None:
    # Arrange
    names = ("submitButton", "counter")

    # Act
    verdicts = tuple(bool(DOM_TYPED_RECEIVER_PATTERN.match(n)) for n in names)

    # Assert
    assert verdicts == (True, False)


def test_temporal_factory_pattern_captures_the_binding() -> None:
    # Arrange
    text = "const start = Temporal.PlainDate.from('2024-01-01');"

    # Act
    found = TEMPORAL_FACTORY_VAR_DECL_PATTERN.search(text)

    # Assert
    assert found is not None
    assert found.group(1) == "start"


def test_name_tables_hold_their_reference_members() -> None:
    # Arrange
    expected = ("add", "Object.groupBy", "Headers", "draft")

    # Act
    found = (
        expected[0] in TEMPORAL_IMMUTABLE_METHODS,
        expected[1] in ES2024_STATIC_NON_MUTATING_FACTORIES,
        expected[2] in WEB_API_TYPED_RECEIVER_TYPES,
        expected[3] in PARAM_REASSIGN_ALLOWLIST,
    )

    # Assert
    assert found == (True, True, True, True)
