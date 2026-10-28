from __future__ import annotations

import struct
from dataclasses import dataclass

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
GIF_SIGNATURES = (b"GIF87a", b"GIF89a")
JPEG_START = b"\xff\xd8"
JPEG_SOF_MARKERS = frozenset(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
JPEG_STANDALONE_MARKERS = frozenset({0x01, *range(0xD0, 0xD9)})
HEADER_READ_LIMIT = 4 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class Dimensions:
    width: int
    height: int

    @property
    def longer_side(self) -> int:
        return max(self.width, self.height)


@dataclass(frozen=True, slots=True)
class ImageFailure:
    reason: str


def _png(data: bytes) -> Dimensions | None:
    if len(data) < 24 or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return Dimensions(width, height)


def _gif(data: bytes) -> Dimensions | None:
    if len(data) < 10:
        return None
    width, height = struct.unpack("<HH", data[6:10])
    return Dimensions(width, height)


def _webp(data: bytes) -> Dimensions | None:
    chunk = data[12:16]
    if chunk == b"VP8 " and len(data) >= 30:
        width, height = struct.unpack("<HH", data[26:30])
        return Dimensions(width & 0x3FFF, height & 0x3FFF)
    if chunk == b"VP8L" and len(data) >= 25:
        bits = int.from_bytes(data[21:25], "little")
        return Dimensions((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
    if chunk == b"VP8X" and len(data) >= 30:
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return Dimensions(width, height)
    return None


def _jpeg_segment(data: bytes, offset: int) -> tuple[int, Dimensions | None]:
    marker = data[offset + 1]
    if marker in JPEG_STANDALONE_MARKERS or marker == 0xFF:
        return offset + (1 if marker == 0xFF else 2), None
    if offset + 4 > len(data):
        return len(data), None
    length = struct.unpack(">H", data[offset + 2 : offset + 4])[0]
    if marker in JPEG_SOF_MARKERS and offset + 9 <= len(data):
        height, width = struct.unpack(">HH", data[offset + 5 : offset + 9])
        return len(data), Dimensions(width, height)
    return offset + 2 + length, None


def _jpeg(data: bytes) -> Dimensions | None:
    offset = 2
    steps = 0
    while offset + 1 < len(data) and data[offset] == 0xFF and steps < len(data):
        offset, found = _jpeg_segment(data, offset)
        if found is not None:
            return found
        steps += 1
    return None


def parse_dimensions(data: bytes) -> Dimensions | None:
    if data.startswith(PNG_SIGNATURE):
        return _png(data)
    if data.startswith(GIF_SIGNATURES):
        return _gif(data)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return _webp(data)
    if data.startswith(JPEG_START):
        return _jpeg(data)
    return None


def read_dimensions(path: str) -> Dimensions | ImageFailure:
    try:
        with open(path, "rb") as handle:
            data = handle.read(HEADER_READ_LIMIT)
    except OSError as error:
        return ImageFailure(f"cannot read: {error.strerror or error}")
    found = parse_dimensions(data)
    if found is None:
        return ImageFailure("not a PNG, JPEG, GIF, or WebP image")
    return found
