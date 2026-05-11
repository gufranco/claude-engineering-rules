"""TypedArray mutation coverage.

Item 120 of the plan. Validates TypedArray methods (set, fill, sort, reverse,
copyWithin) on receivers that look like binary buffers, and confirms hot-path
directories (crypto, codec, image, audio, parser, wasm, ...) skip the
detector entirely.
"""

from __future__ import annotations

import pytest

from conftest import make_write_payload

TYPED_ARRAY_BLOCKED: list[tuple[str, str, str]] = [
    (
        "set",
        "const audioBuffer = new Uint8Array(64)\naudioBuffer.set(other, 0)",
        "typed-array.set",
    ),
    (
        "fill",
        "const pixelBuffer = new Uint8ClampedArray(256)\npixelBuffer.fill(0)",
        "typed-array.fill",
    ),
    ("sort", "const samples = new Float32Array(8)\nsamples.sort()", "typed-array.sort"),
    (
        "reverse",
        "const frame = new Int16Array(8)\nframe.reverse()",
        "typed-array.reverse",
    ),
    (
        "copy-within",
        "const wave = new Float64Array(8)\nwave.copyWithin(0, 4)",
        "typed-array.copyWithin",
    ),
    (
        "float16-fill",
        "const halfBuffer = new Float16Array(16)\nhalfBuffer.fill(0)",
        "typed-array.fill",
    ),
    (
        "float16-set",
        "const halfBuffer = new Float16Array(16)\nhalfBuffer.set(other, 0)",
        "typed-array.set",
    ),
]


@pytest.mark.parametrize(("label", "snippet", "detector"), TYPED_ARRAY_BLOCKED)
def test_typed_array_mutation_blocked_in_app_code(run_hook, label, snippet, detector):
    # Arrange
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{label}: expected block, got {code}\n{stderr}"
    assert detector in stderr, f"{label}: detector {detector} missing"


HOT_PATHS: list[str] = [
    "/repo/src/crypto/cipher.ts",
    "/repo/src/codec/h264.ts",
    "/repo/src/image/png.ts",
    "/repo/src/audio/decoder.ts",
    "/repo/src/parser/binary.ts",
    "/repo/src/wasm/runtime.ts",
    "/repo/src/canvas/render.ts",
    "/repo/src/encoder/jpeg.ts",
    "/repo/src/decoder/h265.ts",
    "/repo/src/simd/sum.ts",
    "/repo/src/webgl/buffer.ts",
    "/repo/src/pixel/blend.ts",
    "/repo/src/hash/sha256.ts",
    "/repo/src/cipher/aes.ts",
]


@pytest.mark.parametrize("path", HOT_PATHS)
def test_typed_array_mutation_skipped_in_hot_path(run_hook, path):
    # Arrange
    snippet = (
        "const buffer = new Uint8Array(64)\nbuffer.set(source, 0)\nbuffer.fill(0)\n"
    )
    payload = make_write_payload(path, snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"hot path {path} unexpectedly blocked\n{stderr}"


def test_typed_array_no_buffer_hint_does_not_trigger(run_hook):
    # Arrange
    snippet = "const value = something.set(key, 1)"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, _ = run_hook(payload)

    # Assert
    assert code == 0


def test_typed_array_immutable_methods_pass(run_hook):
    # Arrange
    snippet = "const audioBuffer = new Uint8Array(64)\nconst sortedBuffer = audioBuffer.toSorted()\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
