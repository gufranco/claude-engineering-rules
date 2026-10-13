from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.mutation_detectors_methods import (  # noqa: E402
    detect_atomics_mutations,
    detect_dataview_setters,
    detect_finalization_registry,
    detect_proxy_mutating_traps,
    detect_uint8array_set_buffer_offset,
    detect_wasm_memory_grow,
    detect_weakref_then_mutate,
)

LEADING_COMMENT = "// a note at the top of the file\n"

CASES = [
    (
        detect_dataview_setters,
        "const view = new DataView(new ArrayBuffer(8));\nview.setInt32(0, 42, true);\n",
        ["web-api.dataview.setInt32"],
    ),
    (
        detect_atomics_mutations,
        "Atomics.store(view, 0, 1);\n",
        ["shared-memory.atomics.store"],
    ),
    (
        detect_wasm_memory_grow,
        "const memory = new WebAssembly.Memory({ initial: 1 });\nmemory.grow(1);\n",
        ["wasm.memory.grow"],
    ),
    (
        detect_uint8array_set_buffer_offset,
        "const buf = new Uint8Array(64);\nconst src = new Uint8Array([1]);\nbuf.set(src, 8);\n",
        ["typed-array.uint8.set-with-offset"],
    ),
    (
        detect_proxy_mutating_traps,
        "const handler = {\n  set(target, key, value) { return true; }\n};\n"
        "const p = new Proxy({}, handler);\n",
        ["proxy.trap.set"],
    ),
    (
        detect_weakref_then_mutate,
        "const list: number[] = [];\nconst ref = new WeakRef(list);\nref.deref()?.push(1);\n",
        ["weakref.deref-mutate.push"],
    ),
    (
        detect_finalization_registry,
        "const registry = new FinalizationRegistry((held: string) => {\n  run(held);\n});\n",
        ["finalization-registry.construct"],
    ),
]


@pytest.mark.parametrize(
    ("detector", "text", "expected"),
    CASES,
    ids=[case[0].__name__ for case in CASES],
)
def test_a_leading_line_comment_does_not_hide_the_rest_of_the_file(
    detector, text, expected
):
    # Arrange
    source = LEADING_COMMENT + text

    # Act
    matches = detector(source, "ts", "src/module.ts")

    # Assert
    assert [m.detector for m in matches] == expected
