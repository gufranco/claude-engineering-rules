from __future__ import annotations

import sys
from pathlib import Path

from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_detectors_binary import (  # noqa: E402
    detect_arraybuffer_transfer,
    detect_atomics_mutations,
    detect_dataview_setters,
    detect_typed_array_mutations,
    detect_uint8_base64_setter,
    detect_uint8array_set_buffer_offset,
    detect_wasm_memory_grow,
)


def _source(faker: Faker) -> str:
    return f"/repo/src/{faker.word()}.ts"


def test_typed_array_mutations_need_a_typed_array_signal(faker: Faker) -> None:
    # Arrange
    text = "items.sort();\n"

    # Act
    hits = detect_typed_array_mutations(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_typed_array_mutations_flag_fill_on_a_typed_array(faker: Faker) -> None:
    # Arrange
    text = "const px = new Uint8Array(4);\npx.fill(0);\n"

    # Act
    hits = detect_typed_array_mutations(text, "ts", _source(faker))

    # Assert
    assert [(h.detector, h.metadata["owner"]) for h in hits] == [
        ("typed-array.fill", "px")
    ]


def test_dataview_setters_flag_a_dataview_write(faker: Faker) -> None:
    # Arrange
    text = "const dv = new DataView(buf);\ndv.setUint16(0, 1);\n"

    # Act
    hits = detect_dataview_setters(text, "ts", _source(faker))

    # Assert
    assert [h.detector for h in hits] == ["web-api.dataview.setUint16"]


def test_dataview_setters_ignore_text_without_a_dataview(faker: Faker) -> None:
    # Arrange
    text = "thing.setUint16(0, 1);\n"

    # Act
    hits = detect_dataview_setters(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_atomics_mutations_flag_an_info_level_store(faker: Faker) -> None:
    # Arrange
    text = "Atomics.store(view, 0, 1);\n"

    # Act
    hits = detect_atomics_mutations(text, "ts", _source(faker))

    # Assert
    assert [(h.detector, h.metadata["severity"]) for h in hits] == [
        ("shared-memory.atomics.store", "info")
    ]


def test_wasm_memory_grow_requires_a_memory_owner(faker: Faker) -> None:
    # Arrange
    text = "const memory = new WebAssembly.Memory({ initial: 1 });\nmemory.grow(1);\nlist.grow(1);\n"

    # Act
    hits = detect_wasm_memory_grow(text, "ts", _source(faker))

    # Assert
    assert [(h.line, h.metadata["owner"]) for h in hits] == [(2, "memory")]


def test_uint8array_set_needs_an_offset_argument(faker: Faker) -> None:
    # Arrange
    text = "const out = new Uint8Array(8);\nout.set(src);\nout.set(f(a, b), 4);\n"

    # Act
    hits = detect_uint8array_set_buffer_offset(text, "ts", _source(faker))

    # Assert
    assert [h.line for h in hits] == [3]


def test_uint8_base64_setter_names_each_variant(faker: Faker) -> None:
    # Arrange
    text = "buf.setFromBase64(a);\nbuf.setFromHex(b);\n"

    # Act
    hits = detect_uint8_base64_setter(text, "ts", _source(faker))

    # Assert
    assert [h.detector for h in hits] == ["uint8.set-from-base64", "uint8.set-from-hex"]


def test_arraybuffer_transfer_needs_an_arraybuffer_hint(faker: Faker) -> None:
    # Arrange
    with_hint = "const b = new ArrayBuffer(8);\nb.transferToFixedLength(4);\n"
    without_hint = "b.transfer();\n"

    # Act
    hits = (
        detect_arraybuffer_transfer(with_hint, "ts", _source(faker)),
        detect_arraybuffer_transfer(without_hint, "ts", _source(faker)),
    )

    # Assert
    assert [h.detector for h in hits[0]] == ["arraybuffer.transfer-to-fixed-length"]
    assert hits[1] == []


def test_uint8array_set_with_an_unclosed_call_is_not_flagged(faker: Faker) -> None:
    # Arrange
    text = "const out = new Uint8Array(8);\nout.set(src\n"

    # Act
    hits = detect_uint8array_set_buffer_offset(text, "ts", _source(faker))

    # Assert
    assert hits == []
