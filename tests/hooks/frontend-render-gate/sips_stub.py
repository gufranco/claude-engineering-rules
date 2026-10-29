#!/usr/bin/env python3
import os
import struct
import sys

MARKER = bytes((0x15, 0xCC, 0xFA))
WHITE = b"\xff\xff\xff"
WIDTH = 360
ROWS = 4


def bmp(marked: int) -> bytes:
    pixels = MARKER * marked + WHITE * (WIDTH * ROWS - marked)
    info = struct.pack("<IiiHHI", 40, WIDTH, -ROWS, 1, 24, 0) + b"\x00" * 20
    header = b"BM" + struct.pack("<IHHI", 54 + len(pixels), 0, 0, 54)
    return header + info + pixels


def main() -> int:
    if os.environ.get("SIPS_STUB_FAIL"):
        print("unsupported image", file=sys.stderr)
        return 1
    marked = int(os.environ.get("SIPS_STUB_MARKED", "540"))
    with open(sys.argv[8], "wb") as handle:
        handle.write(bmp(marked))
    return 0


if __name__ == "__main__":
    sys.exit(main())
