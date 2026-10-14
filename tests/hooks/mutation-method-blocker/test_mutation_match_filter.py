from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_detectors_core import Match  # noqa: E402
from _lib.mutation_match_filter import (  # noqa: E402
    ESLINT_RULES,
    filter_matches,
    is_inside_state_mgmt_scope,
)
from _lib.suppression import compute_block_state  # noqa: E402


def _filter(matches: list[Match], text: str, file_path: str):
    block_state = compute_block_state(text.splitlines(), rules=ESLINT_RULES)
    return filter_matches(matches, text, file_path, block_state)


def test_filter_counts_each_allow_reason() -> None:
    # Arrange
    text = "router.push('/a');\nitems.push(1);\n"
    matches = [
        Match(
            line=1,
            col=1,
            text="router.push('/a');",
            detector="array.push",
            metadata={"owner": "router"},
        ),
        Match(
            line=2,
            col=1,
            text="items.push(1);",
            detector="array.push",
            metadata={"owner": "items"},
        ),
    ]

    # Act
    survived, reasons = _filter(matches, text, "/repo/src/app.ts")

    # Assert
    assert [m.line for m in survived] == [2]
    assert reasons == {"framework-receiver": 1}


def test_filter_drops_everything_under_ts_nocheck() -> None:
    # Arrange
    text = "// @ts-nocheck\nitems.push(1);\n"
    matches = [Match(line=2, col=1, text="items.push(1);", detector="array.push")]

    # Act
    survived, reasons = _filter(matches, text, "/repo/src/app.ts")

    # Assert
    assert survived == []
    assert reasons == {"ts-nocheck": 1}


def test_filter_keeps_scope_exempt_detectors_inside_a_store_file() -> None:
    # Arrange
    text = "total = 3;\n"
    matches = [
        Match(line=1, col=1, text="total = 3;", detector="svelte.derived-reassign")
    ]

    # Act
    survived, reasons = _filter(matches, text, "/repo/src/user.store.ts")

    # Assert
    assert survived == matches
    assert reasons == {}


def test_filter_labels_a_state_management_scope() -> None:
    # Arrange
    text = "items.push(1);\n"
    matches = [Match(line=1, col=1, text="items.push(1);", detector="array.push")]

    # Act
    survived, reasons = _filter(matches, text, "/repo/src/userSlice.ts")

    # Assert
    assert survived == []
    assert reasons == {"state-mgmt:state-mgmt-filename": 1}


def test_scope_returns_out_of_scope_for_a_svelte_raw_receiver() -> None:
    # Arrange
    lines = ["let rows = $state.raw([]);", "rows.push(1);"]

    # Act
    verdict = is_inside_state_mgmt_scope(lines, 1, "/repo/src/list.svelte.ts")

    # Assert
    assert verdict == (False, None)


def test_scope_finds_an_open_atom_with_reducer_callback() -> None:
    # Arrange
    lines = ["const a = atomWithReducer(0, (prev) => {", "  prev.count += 1;"]

    # Act
    verdict = is_inside_state_mgmt_scope(lines, 1, "/repo/src/app.ts")

    # Assert
    assert verdict == (True, "jotai-atomWithReducer")


def test_scope_matches_a_declared_library_receiver() -> None:
    # Arrange
    lines = [
        "import { proxy } from 'valtio';",
        "const store = proxy({});",
        "store.count = 1;",
    ]

    # Act
    verdict = is_inside_state_mgmt_scope(lines, 2, "/repo/src/app.ts")

    # Assert
    assert verdict == (True, "valtio-proxy")
