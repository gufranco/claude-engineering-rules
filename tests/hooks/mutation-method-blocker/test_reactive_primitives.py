from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.mutation_allowlists import (  # noqa: E402
    collect_state_mgmt_receivers,
    is_in_state_mgmt_scope,
    is_state_mgmt_filename,
)


def test_angular_signals_positive() -> None:
    # Arrange
    text = (
        'import { signal, computed } from "@angular/core";\n'
        "const count = signal(0);\n"
        "const double = computed(() => count() * 2);\n"
        "count.set(5);\n"
        "count.update(v => v + 1);\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "app.component.ts")

    # Assert
    assert scope is True
    assert label == "angular-signals"


def test_angular_signals_positive_receivers() -> None:
    # Arrange
    text = (
        'import { signal, computed } from "@angular/core";\n'
        "const count = signal(0);\n"
        "const double = computed(() => count() * 2);\n"
        "count.set(5);\n"
        "count.update(v => v + 1);\n"
    )

    # Act
    receivers = collect_state_mgmt_receivers(text, "app.component.ts")

    # Assert
    assert "angular-signals" in receivers
    assert "count" in receivers["angular-signals"]


def test_angular_signals_negative_without_import() -> None:
    # Arrange
    text = "const count = signal(0);\ncount.set(5);\n"

    # Act
    _scope, label = is_in_state_mgmt_scope(text, "plain.ts")

    # Assert
    assert label != "angular-signals"


def test_angular_signals_negative_without_import_receivers() -> None:
    # Arrange
    text = "const count = signal(0);\ncount.set(5);\n"

    # Act
    receivers = collect_state_mgmt_receivers(text, "plain.ts")

    # Assert
    assert "angular-signals" not in receivers


def test_qwik_signals_positive() -> None:
    # Arrange
    text = (
        'import { useSignal, useStore } from "@builder.io/qwik";\n'
        "const count = useSignal(0);\n"
        "const state = useStore({ items: [] });\n"
        "count.value = 5;\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "counter.tsx")

    # Assert
    assert scope is True
    assert label == "qwik-signals"


def test_qwik_signals_positive_receivers() -> None:
    # Arrange
    text = (
        'import { useSignal, useStore } from "@builder.io/qwik";\n'
        "const count = useSignal(0);\n"
        "const state = useStore({ items: [] });\n"
        "count.value = 5;\n"
    )

    # Act
    receivers = collect_state_mgmt_receivers(text, "counter.tsx")

    # Assert
    assert "count" in receivers["qwik-signals"]


def test_qwik_signals_negative_without_import() -> None:
    # Arrange
    text = "const count = useSignal(0);\ncount.value = 5;\n"

    # Act
    _scope, label = is_in_state_mgmt_scope(text, "comp.tsx")

    # Assert
    assert label != "qwik-signals"


def test_qwik_filename_allowlisted() -> None:
    # Arrange
    file_path = "src/components/counter.qwik.tsx"

    # Act
    result = is_state_mgmt_filename(file_path)

    # Assert
    assert result is True


def test_preact_signals_positive() -> None:
    # Arrange
    text = (
        'import { signal, computed } from "@preact/signals";\n'
        "const count = signal(0);\n"
        "count.value = 5;\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "app.tsx")

    # Assert
    assert scope is True
    assert label == "preact-signals"


def test_preact_signals_positive_receivers() -> None:
    # Arrange
    text = (
        'import { signal, computed } from "@preact/signals";\n'
        "const count = signal(0);\n"
        "count.value = 5;\n"
    )

    # Act
    receivers = collect_state_mgmt_receivers(text, "app.tsx")

    # Assert
    assert "count" in receivers["preact-signals"]


def test_preact_signals_core_positive() -> None:
    # Arrange
    text = (
        'import { signal, batch } from "@preact/signals-core";\n'
        "const x = signal(0);\n"
        "batch(() => { x.value = 1; });\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "core.ts")

    # Assert
    assert scope is True
    assert label == "preact-signals"


def test_preact_signals_react_variant() -> None:
    # Arrange
    text = (
        'import { useSignal } from "@preact/signals-react";\n'
        "const count = useSignal(0);\n"
        "count.value = 5;\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "comp.tsx")

    # Assert
    assert scope is True
    assert label == "preact-signals"


def test_preact_signals_negative_without_import() -> None:
    # Arrange
    text = "const count = signal(0);\ncount.value = 5;\n"

    # Act
    _scope, label = is_in_state_mgmt_scope(text, "plain.ts")

    # Assert
    assert label != "preact-signals"


def test_react_19_useactionstate_recognized() -> None:
    # Arrange
    text = (
        'import { useActionState } from "react";\n'
        "const [state, formAction] = useActionState(reducer, initial);\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "form.tsx")

    # Assert
    assert scope is True
    assert label == "react-19-state-hooks"


def test_react_19_useformstate_recognized() -> None:
    # Arrange
    text = (
        'import { useFormState } from "react-dom";\n'
        "const [state, action] = useFormState(submit, null);\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "form.tsx")

    # Assert
    assert scope is True
    assert label == "react-19-state-hooks"


def test_react_19_useoptimistic_recognized() -> None:
    # Arrange
    text = (
        'import { useOptimistic } from "react";\n'
        "const [optimistic, addOptimistic] = useOptimistic(items);\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "list.tsx")

    # Assert
    assert scope is True
    assert label == "react-19-state-hooks"


def test_react_usereducer_body_recognized() -> None:
    # Arrange
    text = (
        'import { useReducer } from "react";\n'
        "const [state, dispatch] = useReducer(reducer, initial);\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "comp.tsx")

    # Assert
    assert scope is True
    assert label == "react-19-state-hooks"


def test_react_server_action_directive_recognized() -> None:
    # Arrange
    text = (
        '"use server";\n'
        'import { db } from "@/lib/db";\n'
        "async function createPost(formData) {\n"
        "  return db.post.create({ data: { ... } });\n"
        "}\n"
    )

    # Act
    scope, label = is_in_state_mgmt_scope(text, "actions.ts")

    # Assert
    assert scope is True
    assert label == "react-server-action"


def test_react_no_directive_does_not_flag_server_action() -> None:
    # Arrange
    text = (
        'import { db } from "@/lib/db";\n'
        "async function createPost(formData) {\n"
        "  return db.post.create({ data: { ... } });\n"
        "}\n"
    )

    # Act
    _scope, label = is_in_state_mgmt_scope(text, "actions.ts")

    # Assert
    assert label != "react-server-action"
