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
    # Arrange
    snippet = f"const buffer = new {subtype}(1024)\nbuffer.fill(0)\n"
    payload = make_edit_payload("/repo/src/services/payment.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{subtype}: expected block, got exit {code}\n{stderr}"
    assert "typed-array.fill" in stderr, f"{subtype}: detector missing\n{stderr}"


def test_float16_array_es2025_recognized(run_hook):
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
    assert "typed-array.set" in stderr, stderr
    assert "typed-array.fill" in stderr, stderr
    assert "typed-array.sort" in stderr, stderr
    assert "typed-array.reverse" in stderr, stderr


def test_typed_array_hot_path_short_circuit(run_hook):
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


def test_typed_array_allow_marker_does_not_bypass_detector(run_hook):
    # Arrange
    snippet = (
        "const buffer = new Uint8Array(1024)\n"
        "buffer.set([1, 2, 3], 0) // @allow-mutation -- WebGL upload requires stable buffer\n"
    )
    payload = make_edit_payload("/repo/src/business/orders.ts", snippet)

    # Act
    code, _stderr = run_hook(payload)

    # Assert
    assert code == 2


def test_typed_array_eslint_directive_bypasses_detector(run_hook):
    # Arrange
    snippet = (
        "const buffer = new Uint8Array(1024)\n"
        "buffer.set([1, 2, 3], 0) // eslint-disable-line\n"
    )
    payload = make_edit_payload("/repo/src/business/orders.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"tool directive should suppress:\n{stderr}"
