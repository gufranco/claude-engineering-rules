from __future__ import annotations

import shlex
import struct
import sys
from pathlib import Path

from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.change_marker import (  # noqa: E402
    SIPS_ENV,
    MarkerCount,
    MarkerFailure,
    count_marker_pixels,
    read_marker,
)

fake = Faker()
Faker.seed(6107)
MARKER = (0x15, 0xCC, 0xFA)
NEAR = (0x30, 0xB8, 0xE8)
FAR = (0x15, 0xCC, 0x80)
WHITE = (0xFF, 0xFF, 0xFF)


def _bmp(
    rows: list[list[tuple[int, int, int]]], depth: int = 24, pad: bytes = b""
) -> bytes:
    width = len(rows[0])
    size = depth // 8
    stride = (width * size + 3) & ~3
    filler = (pad * stride)[: stride - width * size] if pad else b""
    body = b"".join(
        b"".join(bytes(pixel) + b"\x00" * (size - 3) for pixel in row)
        + filler.ljust(stride - width * size, b"\x00")
        for row in rows
    )
    info = struct.pack("<IiiHHI", 40, width, -len(rows), 1, depth, 0)
    header = b"BM" + struct.pack("<IHHI", 54 + len(body), 0, 0, 54)
    return header + info + b"\x00" * 20 + body


def _image(width: int, height: int, marked: int, colour=MARKER) -> list[list]:
    pixels = [colour] * marked + [WHITE] * (width * height - marked)
    return [pixels[row * width : (row + 1) * width] for row in range(height)]


def _sips_stub(tmp_path: Path, body: str) -> str:
    stub = tmp_path / "sips"
    stub.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    stub.chmod(0o755)
    return str(stub)


def test_counts_every_marker_pixel_in_a_24_bit_image():
    # Arrange
    marked = fake.random_int(20, 60)
    data = _bmp(_image(fake.random_int(30, 50), 4, marked))

    # Act
    result = count_marker_pixels(data)

    # Assert
    assert result == MarkerCount(marked)


def test_counts_marker_pixels_in_a_32_bit_image():
    # Arrange
    marked = fake.random_int(20, 40)
    data = _bmp(_image(25, 3, marked), depth=32)

    # Act
    result = count_marker_pixels(data)

    # Assert
    assert result == MarkerCount(marked)


def test_counts_a_colour_inside_the_tolerance():
    # Arrange
    data = _bmp(_image(10, 3, 7, NEAR))

    # Act
    result = count_marker_pixels(data)

    # Assert
    assert result == MarkerCount(7)


def test_ignores_a_colour_outside_the_tolerance():
    # Arrange
    data = _bmp(_image(10, 3, 9, FAR))

    # Act
    result = count_marker_pixels(data)

    # Assert
    assert result == MarkerCount(0)


def test_ignores_marker_bytes_in_row_padding():
    # Arrange
    data = _bmp([[WHITE, WHITE, WHITE]] * 2, pad=bytes(MARKER))

    # Act
    result = count_marker_pixels(data)

    # Assert
    assert result == MarkerCount(0)


def test_ignores_marker_bytes_that_straddle_two_pixels():
    # Arrange
    straddle = [(0xFF, 0xFF, 0x15), (0xCC, 0xFA, 0xFF), WHITE, WHITE]
    data = _bmp([straddle])

    # Act
    result = count_marker_pixels(data)

    # Assert
    assert result == MarkerCount(0)


def test_rejects_data_that_is_not_a_bmp():
    # Arrange
    data = b"\x89PNG\r\n\x1a\n" + fake.binary(64)

    # Act
    result = count_marker_pixels(data)

    # Assert
    assert result == MarkerFailure("the downscaled copy is not a BMP image")


def test_rejects_an_unsupported_bmp_depth():
    # Arrange
    data = bytearray(_bmp(_image(4, 2, 0)))
    data[28:30] = struct.pack("<H", 8)

    # Act
    result = count_marker_pixels(bytes(data))

    # Assert
    assert result == MarkerFailure("unsupported BMP layout: 8 bits, mode 0")


def test_reads_the_marker_through_a_downscaled_copy(tmp_path, monkeypatch):
    # Arrange
    sample = tmp_path / "sample.bmp"
    sample.write_bytes(_bmp(_image(30, 2, 24)))
    monkeypatch.setenv(SIPS_ENV, _sips_stub(tmp_path, f'cp -f "{sample}" "$8"'))
    source = tmp_path / "after.png"
    source.write_bytes(fake.binary(32))

    # Act
    result = read_marker(str(source))

    # Assert
    assert result == MarkerCount(24)


def test_runs_a_sips_command_given_with_arguments(tmp_path, monkeypatch):
    # Arrange
    sample = tmp_path / "sample.bmp"
    sample.write_bytes(_bmp(_image(30, 2, 21)))
    script = tmp_path / "fake sips.py"
    script.write_text(
        f"import shutil, sys\nshutil.copyfile({str(sample)!r}, sys.argv[8])\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        SIPS_ENV, f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"
    )

    # Act
    result = read_marker(str(tmp_path / "after.png"))

    # Assert
    assert result == MarkerCount(21)


def test_names_a_sips_failure(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setenv(SIPS_ENV, _sips_stub(tmp_path, "echo broken >&2; exit 3"))

    # Act
    result = read_marker(str(tmp_path / "after.png"))

    # Assert
    assert result == MarkerFailure("sips exited 3: broken")


def test_names_a_missing_sips_binary(tmp_path, monkeypatch):
    # Arrange
    missing = tmp_path / "absent" / "sips"
    monkeypatch.setenv(SIPS_ENV, str(missing))

    # Act
    result = read_marker(str(tmp_path / "after.png"))

    # Assert
    assert isinstance(result, MarkerFailure)
    assert result.reason.startswith("cannot downscale with sips: ")
    assert str(missing) in result.reason


def test_names_a_sips_run_that_wrote_nothing(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setenv(SIPS_ENV, _sips_stub(tmp_path, "exit 0"))

    # Act
    result = read_marker(str(tmp_path / "after.png"))

    # Assert
    assert result == MarkerFailure("sips wrote no image: No such file or directory")
