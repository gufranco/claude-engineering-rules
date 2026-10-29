from __future__ import annotations

import os
import re
import struct
import subprocess
import tempfile
from dataclasses import dataclass

MARKER_HEX = "#FACC15"
MARKER_BGR = (0x15, 0xCC, 0xFA)
CHANNEL_TOLERANCE = 48
MIN_MARKER_PIXELS = 20
SAMPLE_WIDTH_PX = 360
SIPS_ENV = "CHANGE_MARKER_SIPS"
SIPS_TIMEOUT_SECONDS = 30
BMP_HEADER_BYTES = 34
BMP_DEPTHS = frozenset({24, 32})
BMP_COMPRESSIONS = frozenset({0, 3})


@dataclass(frozen=True, slots=True)
class MarkerCount:
    pixels: int


@dataclass(frozen=True, slots=True)
class MarkerFailure:
    reason: str


def _byte_range(center: int) -> bytes:
    low = max(0, center - CHANNEL_TOLERANCE)
    high = min(0xFF, center + CHANNEL_TOLERANCE)
    return b"[" + re.escape(bytes([low])) + b"-" + re.escape(bytes([high])) + b"]"


MARKER_PIXEL = re.compile(
    b"(?=" + b"".join(_byte_range(channel) for channel in MARKER_BGR) + b")",
    re.DOTALL,
)


def _layout(data: bytes) -> tuple[int, int, int, int] | MarkerFailure:
    if len(data) < BMP_HEADER_BYTES or data[:2] != b"BM":
        return MarkerFailure("the downscaled copy is not a BMP image")
    offset = struct.unpack("<I", data[10:14])[0]
    width, height, _, depth, compression = struct.unpack("<iiHHI", data[18:34])
    if depth not in BMP_DEPTHS or compression not in BMP_COMPRESSIONS or width <= 0:
        return MarkerFailure(
            f"unsupported BMP layout: {depth} bits, mode {compression}"
        )
    return offset, width, abs(height), depth // 8


def count_marker_pixels(data: bytes) -> MarkerCount | MarkerFailure:
    layout = _layout(data)
    if isinstance(layout, MarkerFailure):
        return layout
    offset, width, rows, size = layout
    stride = (width * size + 3) & ~3
    end = min(len(data), offset + stride * rows)
    found = 0
    for match in MARKER_PIXEL.finditer(data, offset, end):
        column = (match.start() - offset) % stride
        if column % size == 0 and column < width * size:
            found += 1
    return MarkerCount(found)


def _downscale(path: str, target: str) -> str | None:
    command = [
        os.environ.get(SIPS_ENV, "sips"),
        "-s",
        "format",
        "bmp",
        "--resampleWidth",
        str(SAMPLE_WIDTH_PX),
        path,
        "--out",
        target,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=SIPS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"cannot downscale with sips: {error}"
    if result.returncode != 0:
        return f"sips exited {result.returncode}: {result.stderr.strip()[:200]}"
    return None


def read_marker(path: str) -> MarkerCount | MarkerFailure:
    with tempfile.TemporaryDirectory(prefix="change-marker-") as scratch:
        target = os.path.join(scratch, "sample.bmp")
        failure = _downscale(path, target)
        if failure is not None:
            return MarkerFailure(failure)
        try:
            with open(target, "rb") as handle:
                data = handle.read()
        except OSError as error:
            return MarkerFailure(f"sips wrote no image: {error.strerror or error}")
    return count_marker_pixels(data)
