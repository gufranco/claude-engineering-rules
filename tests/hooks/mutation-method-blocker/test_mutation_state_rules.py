from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_state_rules import RECEIVER_RULES, SCOPE_RULES  # noqa: E402


def _first_scope_label(window: str, file_path: str) -> str | None:
    return next((label for label, rule in SCOPE_RULES if rule(window, file_path)), None)


def test_scope_rules_prefer_solid_reconcile_over_solid_produce() -> None:
    # Arrange
    window = "import { reconcile } from 'solid-js/store';\nsetStore(reconcile(next));"

    # Act
    label = _first_scope_label(window, "/repo/src/app.ts")

    # Assert
    assert label == "solid-reconcile"


def test_scope_rules_fall_back_to_solid_produce() -> None:
    # Arrange
    window = "import { produce } from 'solid-js/store';\nconst raw = unwrap(store);"

    # Act
    label = _first_scope_label(window, "/repo/src/app.ts")

    # Assert
    assert label == "solid-produce"


def test_svelte_runes_rule_needs_a_svelte_file() -> None:
    # Arrange
    window = "let count = $state(0);"

    # Act
    labels = (
        _first_scope_label(window, "/repo/src/counter.svelte.ts"),
        _first_scope_label(window, "/repo/src/counter.ts"),
    )

    # Assert
    assert labels == ("svelte-runes", None)


def test_effect_ts_rule_needs_the_import_and_a_generator_or_ref() -> None:
    # Arrange
    window = "import { Effect } from 'effect';\nconst p = Effect.gen(function* () {"

    # Act
    label = _first_scope_label(window, "/repo/src/app.ts")

    # Assert
    assert label == "effect-ts"


def test_receiver_rules_keep_their_declared_order() -> None:
    # Arrange
    expected = (
        "valtio-proxy",
        "solid-store",
        "legendapp-state",
        "vue-reactive",
        "nanostores",
        "svelte-runes",
        "angular-signals",
        "qwik-signals",
        "preact-signals",
        "tc39-signals",
    )

    # Act
    labels = tuple(label for label, _gate, _decls in RECEIVER_RULES)

    # Assert
    assert labels == expected


def test_svelte_receiver_gate_reads_the_file_path() -> None:
    # Arrange
    gate = dict((label, gate) for label, gate, _decls in RECEIVER_RULES)["svelte-runes"]

    # Act
    verdicts = (gate("", "/repo/a.svelte"), gate("", ""), gate("", "/repo/a.ts"))

    # Assert
    assert verdicts == (True, False, False)
