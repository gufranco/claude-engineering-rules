from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_state_patterns import (  # noqa: E402
    IMMER_PRODUCE_PATTERN,
    JOTAI_CALLBACK_OPENER_PATTERN,
    STATE_MGMT_FILENAME_PATTERNS,
    SVELTE_STATE_RAW_VAR_DECL_PATTERN,
    VALTIO_VAR_DECL_PATTERN,
)


def test_filename_patterns_match_a_slice_file_only() -> None:
    # Arrange
    paths = ("src/userSlice.ts", "src/slicer.ts")

    # Act
    verdicts = tuple(
        any(p.search(path) for p in STATE_MGMT_FILENAME_PATTERNS) for path in paths
    )

    # Assert
    assert verdicts == (True, False)


def test_immer_produce_pattern_matches_a_draft_callback() -> None:
    # Arrange
    window = "const next = produce(state, (draft) => {"

    # Act
    found = IMMER_PRODUCE_PATTERN.search(window)

    # Assert
    assert found is not None


def test_valtio_declaration_pattern_captures_the_proxy_binding() -> None:
    # Arrange
    text = "const store = proxy({ count: 0 });"

    # Act
    found = VALTIO_VAR_DECL_PATTERN.search(text)

    # Assert
    assert found is not None
    assert found.group(1) == "store"


def test_svelte_raw_and_jotai_opener_patterns_match_their_syntax() -> None:
    # Arrange
    raw_decl = "let rows = $state.raw([]);"
    opener = "const counter = atomWithReducer(0, reducer);"

    # Act
    found = (
        SVELTE_STATE_RAW_VAR_DECL_PATTERN.search(raw_decl),
        JOTAI_CALLBACK_OPENER_PATTERN.search(opener),
    )

    # Assert
    assert found[0] is not None
    assert found[0].group(1) == "rows"
    assert found[1] is not None
