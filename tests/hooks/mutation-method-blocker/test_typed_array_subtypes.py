"""TypedArray expansion coverage.

Items 210-218 of the plan. Verifies the hook:

  * Recognizes all 12 TypedArray subtypes (Int8, Uint8, Uint8Clamped,
    Int16, Uint16, Int32, Uint32, Float16, Float32, Float64, BigInt64,
    BigUint64) per D37.
  * Watches the five mutating methods: set, fill, sort, reverse, copyWithin.
  * Recognizes ES2025 Float16Array.
  * Allowlists hot-path directories (crypto, codec, image, audio, parser,
    decoder, encoder, wasm, canvas, pixel, simd, webgl, hash, cipher,
    dsp, signal, fft, ml, tensor) and never flags TypedArray mutation in
    those paths.
  * Flags identical TypedArray mutation in business-logic paths.
  * Short-circuits the path-based allowlist before any expensive analysis.
"""

from __future__ import annotations

import pytest

from conftest import make_edit_payload

TYPED_ARRAY_SUBTYPES: list[str] = [
    "Int8Array",
    "Uint8Array",
    "Uint8ClampedArray",
    "Int16Array",
    "Uint16Array",
    "Int32Array",
    "Uint32Array",
    "Float16Array",
    "Float32Array",
    "Float64Array",
    "BigInt64Array",
    "BigUint64Array",
]


@pytest.mark.parametrize("subtype", TYPED_ARRAY_SUBTYPES)
def test_typed_array_set_in_business_path_blocked(run_hook, subtype):
    """Item 213: each of the 12 TypedArray subtypes triggers the detector
    in a non-hot-path directory.
    """
    # Arrange
    snippet = f"const buffer = new {subtype}(1024)\nbuffer.set([1, 2, 3], 0)\n"
    payload = make_edit_payload("/repo/src/business/orders.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{subtype}: expected block, got exit {code}\n{stderr}"
    assert "typed-array.set" in stderr, f"{subtype}: detector missing\n{stderr}"


@pytest.mark.parametrize("subtype", TYPED_ARRAY_SUBTYPES)
def test_typed_array_fill_in_business_path_blocked(run_hook, subtype):
    """Items 211, 213: TypedArray.fill is one of the watched methods."""
    # Arrange
    snippet = f"const buffer = new {subtype}(1024)\nbuffer.fill(0)\n"
    payload = make_edit_payload("/repo/src/services/payment.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{subtype}: expected block, got exit {code}\n{stderr}"
    assert "typed-array.fill" in stderr, f"{subtype}: detector missing\n{stderr}"


def test_float16_array_es2025_recognized(run_hook):
    """Item 214: Float16Array (ES2025) is recognized as a TypedArray."""
    # Arrange
    snippet = "const halfFloats = new Float16Array(buffer)\nhalfFloats.fill(0.5)\n"
    payload = make_edit_payload("/repo/src/business/dashboard.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"Float16Array: expected block, got exit {code}\n{stderr}"
    assert "typed-array.fill" in stderr, f"detector missing in:\n{stderr}"


HOT_PATH_DIRECTORIES: list[str] = [
    "/repo/src/crypto/aes.ts",
    "/repo/src/cipher/rsa.ts",
    "/repo/src/hash/sha256.ts",
    "/repo/src/codec/base64.ts",
    "/repo/src/decoder/utf8.ts",
    "/repo/src/encoder/utf8.ts",
    "/repo/src/image/png.ts",
    "/repo/src/audio/pcm.ts",
    "/repo/src/parser/wasm.ts",
    "/repo/src/wasm/runtime.ts",
    "/repo/src/canvas/draw.ts",
    "/repo/src/pixel/buffer.ts",
    "/repo/src/simd/vector.ts",
    "/repo/src/webgl/shader.ts",
    "/repo/src/dsp/filter.ts",
    "/repo/src/signal/processor.ts",
    "/repo/src/fft/transform.ts",
    "/repo/src/ml/inference.ts",
    "/repo/src/tensor/ops.ts",
]


@pytest.mark.parametrize("hot_path", HOT_PATH_DIRECTORIES)
def test_typed_array_in_hot_path_allowed(run_hook, hot_path):
    """Items 212, 215: TypedArray mutations in hot-path directories are
    allowlisted. The orchestrator short-circuits the detector for these
    paths so crypto, codec, image, etc. never trip.
    """
    # Arrange
    snippet = (
        "const buffer = new Uint8Array(1024)\n"
        "buffer.set([0xAA, 0xBB, 0xCC], 0)\n"
        "buffer.fill(0)\n"
        "buffer.sort()\n"
        "buffer.reverse()\n"
        "buffer.copyWithin(0, 8, 16)\n"
    )
    payload = make_edit_payload(hot_path, snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"{hot_path}: unexpected block\n{stderr}"


def test_typed_array_in_business_path_flagged_full_method_set(run_hook):
    """Item 216: TypedArray mutation in a non-hot-path business directory
    triggers the detector for every watched method.
    """
    # Arrange
    snippet = (
        "const buffer = new Uint8Array(1024)\n"
        "buffer.set([1, 2, 3], 0)\n"
        "buffer.fill(0)\n"
        "buffer.sort()\n"
        "buffer.reverse()\n"
    )
    payload = make_edit_payload("/repo/src/business/orders.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"expected block, got exit {code}\n{stderr}"
    for method in ("set", "fill", "sort", "reverse"):
        assert f"typed-array.{method}" in stderr, (
            f"typed-array.{method} missing in:\n{stderr}"
        )


def test_typed_array_hot_path_short_circuit(run_hook):
    """Item 218: the path-based allowlist short-circuits before any
    expensive analysis. The detector must not be called for hot-path
    files; we verify by asserting zero TypedArray hits in stderr even
    when the file contains many mutations.
    """
    # Arrange
    snippet = (
        "\n".join(f"buffer{i}.set([{i}, {i + 1}], 0)" for i in range(50))
        + "\n"
        + "\n".join(f"const buffer{i} = new Uint8Array({i * 10})" for i in range(50))
    )
    payload = make_edit_payload("/repo/src/crypto/cipher.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"hot-path short-circuit failed:\n{stderr}"
    assert "typed-array" not in stderr


HOT_PATH_NAME_DIRECTORIES: list[str] = [
    "/repo/src/dsp/iir.ts",
    "/repo/src/signal/fir.ts",
    "/repo/src/fft/cooley-tukey.ts",
    "/repo/src/ml/forward-pass.ts",
    "/repo/src/tensor/matmul.ts",
]


@pytest.mark.parametrize("hot_path", HOT_PATH_NAME_DIRECTORIES)
def test_new_hot_paths_dsp_signal_fft_ml_tensor_allowed(run_hook, hot_path):
    """Item 212: dsp, signal, fft, ml, tensor were added to the hot-path
    list. Verify each new directory triggers the allowlist.
    """
    # Arrange
    snippet = (
        "const samples = new Float32Array(1024)\n"
        "samples.fill(0)\n"
        "samples.set(window, 0)\n"
    )
    payload = make_edit_payload(hot_path, snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"{hot_path}: unexpected block\n{stderr}"


def test_typed_array_suppression_marker_bypasses_detector(run_hook):
    """Per-line suppression marker honored on TypedArray mutations."""
    # Arrange
    snippet = (
        "const buffer = new Uint8Array(1024)\n"
        "buffer.set([1, 2, 3], 0) // @claude-allow-mutation -- WebGL upload requires stable buffer\n"
    )
    payload = make_edit_payload("/repo/src/business/orders.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"suppression failed:\n{stderr}"
