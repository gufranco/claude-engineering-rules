"""Phase 34 integration tests: DataView, Atomics, WASM, Proxy, WeakRef, FinalizationRegistry.

Each test exercises a single detector by feeding a minimal TypeScript snippet
through the hook orchestrator and asserting on the resulting `Match.detector`
tag. The fixtures live in `tests/corpus/mutation-method-blocker/wasm_atomics/`
and are imported via the conftest helpers.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mutation_detectors_methods import (  # noqa: E402
    detect_atomics_mutations,
    detect_dataview_setters,
    detect_finalization_registry,
    detect_proxy_mutating_traps,
    detect_uint8array_set_buffer_offset,
    detect_wasm_memory_grow,
    detect_weakref_then_mutate,
)


def test_dataview_setint32_flagged() -> None:
    # Arrange
    text = (
        "const buffer = new ArrayBuffer(64);\n"
        "const view = new DataView(buffer);\n"
        "view.setInt32(0, 42, true);\n"
    )

    # Act
    matches = detect_dataview_setters(text, "ts", "src/protocol.ts")

    # Assert
    assert any(m.detector == "web-api.dataview.setInt32" for m in matches)


def test_dataview_setfloat64_flagged() -> None:
    # Arrange
    text = "const view: DataView = makeView();\nview.setFloat64(8, 3.14, false);\n"

    # Act
    matches = detect_dataview_setters(text, "ts", "src/codec/audio.ts")

    # Assert
    assert any(m.detector == "web-api.dataview.setFloat64" for m in matches)


def test_dataview_setter_without_receiver_hint_is_quiet() -> None:
    # Arrange
    text = "foo.setInt32(0, 1, true);\n"

    # Act
    matches = detect_dataview_setters(text, "ts", "src/widget.ts")

    # Assert
    assert matches == []


def test_uint8array_two_arg_set_flagged() -> None:
    # Arrange
    text = (
        "const buf = new Uint8Array(64);\n"
        "const src = new Uint8Array([1, 2, 3]);\n"
        "buf.set(src, 8);\n"
    )

    # Act
    matches = detect_uint8array_set_buffer_offset(text, "ts", "src/codec/frame.ts")

    # Assert
    assert any(m.detector == "typed-array.uint8.set-with-offset" for m in matches)


def test_uint8array_one_arg_set_not_flagged_by_offset_detector() -> None:
    # Arrange
    text = (
        "const buf = new Uint8Array(64);\n"
        "const src = new Uint8Array([1, 2, 3]);\n"
        "buf.set(src);\n"
    )

    # Act
    matches = detect_uint8array_set_buffer_offset(text, "ts", "src/codec/frame.ts")

    # Assert
    assert matches == []


def test_atomics_store_flagged_as_info() -> None:
    # Arrange
    text = "Atomics.store(view, 0, 1);\n"

    # Act
    matches = detect_atomics_mutations(text, "ts", "src/worker.ts")

    # Assert
    assert any(m.detector == "shared-memory.atomics.store" for m in matches)
    for m in matches:
        assert m.metadata.get("severity") == "info"


def test_atomics_compareexchange_flagged() -> None:
    # Arrange
    text = "Atomics.compareExchange(view, 0, 1, 2);\n"

    # Act
    matches = detect_atomics_mutations(text, "ts", "src/worker.ts")

    # Assert
    assert any(m.detector == "shared-memory.atomics.compareExchange" for m in matches)


def test_atomics_load_not_flagged() -> None:
    # Arrange
    text = "const v = Atomics.load(view, 0);\n"

    # Act
    matches = detect_atomics_mutations(text, "ts", "src/worker.ts")

    # Assert
    assert matches == []


def test_wasm_memory_grow_flagged() -> None:
    # Arrange
    text = "const memory = new WebAssembly.Memory({ initial: 1 });\nmemory.grow(1);\n"

    # Act
    matches = detect_wasm_memory_grow(text, "ts", "src/wasm-host.ts")

    # Assert
    assert any(m.detector == "wasm.memory.grow" for m in matches)


def test_unrelated_grow_call_not_flagged() -> None:
    # Arrange
    text = "tree.grow(1);\n"

    # Act
    matches = detect_wasm_memory_grow(text, "ts", "src/garden.ts")

    # Assert
    assert matches == []


def test_proxy_set_trap_flagged() -> None:
    # Arrange
    text = (
        "const handler = {\n"
        "  set(target, key, value) { return true; }\n"
        "};\n"
        "const p = new Proxy({}, handler);\n"
    )

    # Act
    matches = detect_proxy_mutating_traps(text, "ts", "src/proxy.ts")

    # Assert
    assert any(m.detector == "proxy.trap.set" for m in matches)


def test_proxy_delete_property_trap_flagged() -> None:
    # Arrange
    text = (
        "const handler = {\n"
        "  deleteProperty(target, key) { return true; }\n"
        "};\n"
        "const p = new Proxy({}, handler);\n"
    )

    # Act
    matches = detect_proxy_mutating_traps(text, "ts", "src/proxy.ts")

    # Assert
    assert any(m.detector == "proxy.trap.deleteProperty" for m in matches)


def test_proxy_trap_outside_handler_context_quiet() -> None:
    # Arrange
    text = "function set(value: number) { return value + 1; }\n"

    # Act
    matches = detect_proxy_mutating_traps(text, "ts", "src/util.ts")

    # Assert
    assert matches == []


def test_weakref_deref_push_flagged() -> None:
    # Arrange
    text = (
        "const list: number[] = [];\n"
        "const ref = new WeakRef(list);\n"
        "ref.deref()?.push(1);\n"
    )

    # Act
    matches = detect_weakref_then_mutate(text, "ts", "src/registry.ts")

    # Assert
    assert any(m.detector == "weakref.deref-mutate.push" for m in matches)


def test_weakref_deref_read_only_not_flagged() -> None:
    # Arrange
    text = (
        "const list = [1, 2, 3];\n"
        "const ref = new WeakRef(list);\n"
        "const head = ref.deref()?.at(0);\n"
    )

    # Act
    matches = detect_weakref_then_mutate(text, "ts", "src/registry.ts")

    # Assert
    assert matches == []


def test_finalization_registry_construction_flagged_as_info() -> None:
    # Arrange
    text = (
        "const registry = new FinalizationRegistry((heldValue: string) => {\n"
        "  /* cleanup */\n"
        "});\n"
    )

    # Act
    matches = detect_finalization_registry(text, "ts", "src/cache.ts")

    # Assert
    assert any(m.detector == "finalization-registry.construct" for m in matches)
    for m in matches:
        assert m.metadata.get("severity") == "info"
