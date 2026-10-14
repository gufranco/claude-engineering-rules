from __future__ import annotations

import sys
from pathlib import Path

from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_detectors_transactions import (  # noqa: E402
    detect_automerge_direct_mutation,
    detect_mobx_observable_outside_action,
    detect_xstate_non_assign_context_write,
    detect_yjs_mutation_outside_transact,
)


def _source(faker: Faker) -> str:
    return f"/repo/src/{faker.word()}.ts"


def test_xstate_context_write_outside_assign_is_flagged(faker: Faker) -> None:
    # Arrange
    text = (
        "import { createMachine } from 'xstate';\n"
        "const bump = ({ context }) => { context.count = 1; };\n"
        "const ok = assign(({ context }) => {\n"
        "  context.count = 2;\n"
        "});\n"
    )

    # Act
    hits = detect_xstate_non_assign_context_write(text, "ts", _source(faker))

    # Assert
    assert [(h.line, h.metadata["chain"]) for h in hits] == [(2, "count")]


def test_xstate_without_an_import_is_clean(faker: Faker) -> None:
    # Arrange
    text = "// xstate\ncontext.count = 1;\n"

    # Act
    hits = detect_xstate_non_assign_context_write(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_mobx_write_outside_an_action_is_flagged(faker: Faker) -> None:
    # Arrange
    text = (
        "import { configure, observable, runInAction } from 'mobx';\n"
        "configure({ enforceActions: 'always' });\n"
        "const store = observable({ count: 0 });\n"
        "store.count = 1;\n"
        "runInAction(() => {\n"
        "  store.count = 2;\n"
        "});\n"
    )

    # Act
    hits = detect_mobx_observable_outside_action(text, "ts", _source(faker))

    # Assert
    assert [(h.line, h.metadata["chain"]) for h in hits] == [(4, ".count")]


def test_mobx_without_strict_mode_is_clean(faker: Faker) -> None:
    # Arrange
    text = "import { observable } from 'mobx';\nconst store = observable({});\nstore.count = 1;\n"

    # Act
    hits = detect_mobx_observable_outside_action(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_yjs_write_outside_transact_is_flagged(faker: Faker) -> None:
    # Arrange
    text = (
        "import * as Y from 'yjs';\n"
        "const ymap = doc.getMap('m');\n"
        "ymap.set('a', 1);\n"
        "doc.transact(() => {\n"
        "  ymap.set('b', 2);\n"
        "});\n"
    )

    # Act
    hits = detect_yjs_mutation_outside_transact(text, "ts", _source(faker))

    # Assert
    assert [(h.line, h.metadata["method"]) for h in hits] == [(3, "set")]


def test_automerge_direct_write_is_flagged(faker: Faker) -> None:
    # Arrange
    text = (
        "import * as Automerge from '@automerge/automerge';\n"
        "let doc = Automerge.init();\n"
        "doc.title = 'x';\n"
    )

    # Act
    hits = detect_automerge_direct_mutation(text, "ts", _source(faker))

    # Assert
    assert [(h.line, h.metadata["chain"]) for h in hits] == [(3, ".title")]


def test_automerge_without_an_import_is_clean(faker: Faker) -> None:
    # Arrange
    text = "let doc = Automerge.init();\ndoc.title = 'x';\n"

    # Act
    hits = detect_automerge_direct_mutation(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_yjs_without_a_crdt_declaration_is_clean(faker: Faker) -> None:
    # Arrange
    text = "import * as Y from 'yjs';\nymap.set('a', 1);\n"

    # Act
    hits = detect_yjs_mutation_outside_transact(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_mobx_strict_mode_without_an_observable_is_clean(faker: Faker) -> None:
    # Arrange
    text = (
        "import { configure } from 'mobx';\n"
        "configure({ enforceActions: 'always' });\n"
        "store.count = 1;\n"
    )

    # Act
    hits = detect_mobx_observable_outside_action(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_automerge_import_without_a_document_is_clean(faker: Faker) -> None:
    # Arrange
    text = "import * as Automerge from '@automerge/automerge';\ndoc.title = 'x';\n"

    # Act
    hits = detect_automerge_direct_mutation(text, "ts", _source(faker))

    # Assert
    assert hits == []
