from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.mutation_detectors_assignments import (  # noqa: E402
    detect_mobx_observable_outside_action,
)

PRELUDE = (
    "import { configure, observable, runInAction } from 'mobx';\n"
    "configure({ enforceActions: 'always' });\n"
    "const store = observable({ count: 0 });\n"
)


def test_a_multi_line_comment_inside_an_action_does_not_close_its_scope():
    # Arrange
    source = PRELUDE + (
        "runInAction(() => {\n"
        "  /* closes ) ) )\n"
        "     still ) inside */\n"
        "  store.count = 1;\n"
        "});\n"
    )

    # Act
    matches = detect_mobx_observable_outside_action(source, "ts", "src/store-user.ts")

    # Assert
    assert matches == []


def test_a_write_after_the_action_closes_is_still_flagged():
    # Arrange
    source = (
        PRELUDE + "runInAction(() => {\n  store.count = 1;\n});\nstore.count = 2;\n"
    )

    # Act
    matches = detect_mobx_observable_outside_action(source, "ts", "src/store-user.ts")

    # Assert
    assert [m.line for m in matches] == [7]
