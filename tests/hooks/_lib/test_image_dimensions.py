from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.image_dimensions import (  # noqa: E402
    Dimensions,
    ImageFailure,
    parse_dimensions,
    read_dimensions,
)

fake = Faker()
Faker.seed(4211)


def _png(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR"
        + struct.pack(">II", width, height)
    )


def _gif(width: int, height: int) -> bytes:
    return b"GIF89a" + struct.pack("<HH", width, height)


def _webp(chunk: bytes, body: bytes) -> bytes:
    return b"RIFF" + b"\x00" * 4 + b"WEBP" + chunk + body


def _vp8(width: int, height: int) -> bytes:
    return _webp(b"VP8 ", b"\x00" * 10 + struct.pack("<HH", width, height))


def _vp8l(width: int, height: int) -> bytes:
    bits = (width - 1) | ((height - 1) << 14)
    return _webp(b"VP8L", b"\x00" * 5 + bits.to_bytes(4, "little"))


def _vp8x(width: int, height: int) -> bytes:
    body = (
        b"\x00" * 8
        + (width - 1).to_bytes(3, "little")
        + (height - 1).to_bytes(3, "little")
    )
    return _webp(b"VP8X", body)


def _jpeg(width: int, height: int) -> bytes:
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"\x00" * 14
    restart = b"\xff\xd0"
    padding = b"\xff\xff"
    sof = b"\xff\xc0" + struct.pack(">HBHH", 17, 8, height, width) + b"\x00" * 10
    return b"\xff\xd8" + app0 + restart + padding + sof


def _size() -> tuple[int, int]:
    return fake.pyint(min_value=1, max_value=8000), fake.pyint(
        min_value=1, max_value=8000
    )


@pytest.mark.parametrize("build", [_png, _gif, _vp8, _vp8l, _vp8x, _jpeg])
def test_parse_dimensions_reads_width_and_height_from_each_format(build):
    # Arrange
    width, height = _size()

    # Act
    result = parse_dimensions(build(width, height))

    # Assert
    assert result == Dimensions(width, height)


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"not an image at all",
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 4,
        b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIDAT" + b"\x00" * 8,
        b"GIF89a\x01",
        _webp(b"VP8 ", b"\x00"),
        _webp(b"VP8L", b"\x00"),
        _webp(b"VP8X", b"\x00"),
        _webp(b"ALPH", b"\x00" * 20),
        b"\xff\xd8",
        b"\xff\xd8\x00\x00",
        b"\xff\xd8\xff\xe0\x00",
        b"\xff\xd8\xff\xe0\x00\x02",
    ],
)
def test_parse_dimensions_returns_none_for_truncated_or_unknown_data(data):
    # Arrange
    payload = data

    # Act
    result = parse_dimensions(payload)

    # Assert
    assert result is None


def test_longer_side_picks_the_larger_axis():
    # Arrange
    dimensions = Dimensions(1170, 2532)

    # Act
    result = dimensions.longer_side

    # Assert
    assert result == 2532


def test_read_dimensions_reads_a_file_from_disk(tmp_path):
    # Arrange
    path = tmp_path / f"{fake.word()}.png"
    path.write_bytes(_png(2880, 1800))

    # Act
    result = read_dimensions(str(path))

    # Assert
    assert result == Dimensions(2880, 1800)


def test_read_dimensions_names_a_missing_file(tmp_path):
    # Arrange
    path = tmp_path / f"{fake.word()}.png"

    # Act
    result = read_dimensions(str(path))

    # Assert
    assert result == ImageFailure("cannot read: No such file or directory")


def test_read_dimensions_names_an_unknown_format(tmp_path):
    # Arrange
    path = tmp_path / f"{fake.word()}.mp4"
    path.write_bytes(fake.binary(length=64))

    # Act
    result = read_dimensions(str(path))

    # Assert
    assert result == ImageFailure("not a PNG, JPEG, GIF, or WebP image")
