"""Pack PNG images into a Windows .ico (the desktop shortcut's icon, dubber/assets/dubber.ico).

    node render.js            # PNGs of dubber/assets/logo.svg at each size (Chromium, see docs/STATUS.md)
    .venv/bin/python tools/make_icon.py dubber/assets/dubber.ico logo-16.png logo-32.png … logo-256.png

Each PNG is stored as is (PNG-in-ICO, supported since Windows Vista); the size comes from the PNG header.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path


def png_size(data: bytes) -> tuple[int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    return struct.unpack(">II", data[16:24])


def make_ico(pngs: list[bytes]) -> bytes:
    images = sorted(pngs, key=png_size)
    header = struct.pack("<HHH", 0, 1, len(images))
    entries, offset = b"", 6 + 16 * len(images)
    for data in images:
        w, h = png_size(data)
        # 256 px is written as 0 in the one-byte width/height fields
        entries += struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return header + entries + b"".join(images)


def main() -> None:
    out, *inputs = sys.argv[1:]
    Path(out).write_bytes(make_ico([Path(p).read_bytes() for p in inputs]))


if __name__ == "__main__":
    main()
