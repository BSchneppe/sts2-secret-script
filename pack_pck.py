#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow"]
# ///
"""Packs files into a Godot 4.5 PCK (format version 3).

PNG files are automatically converted to Godot .ctex format (lossless WebP).
Other files (JSON, etc.) are included as-is.
"""

import hashlib
import io
import struct
import sys
from pathlib import Path

from PIL import Image

MAGIC = b"GDPC"
FORMAT_VERSION = 3
ENGINE_MAJOR = 4
ENGINE_MINOR = 5
ENGINE_PATCH = 1
PACK_REL_FILEBASE = 0x02
ALIGNMENT = 32
RESERVED_COUNT = 16

# ctex constants
CTEX_MAGIC = b"GST2"
CTEX_VERSION = 1
CTEX_FLAGS = 0x0D000000  # lossless, no mipmaps, no vram texture
CTEX_DATA_FORMAT = 2  # RGBA8-like
CTEX_IMAGE_FORMAT = 5  # WebP


def align(pos: int, boundary: int = ALIGNMENT) -> int:
    remainder = pos % boundary
    return (boundary - remainder) % boundary


def png_to_ctex(png_data: bytes) -> bytes:
    """Convert a PNG image to Godot's .ctex format (lossless WebP)."""
    img = Image.open(io.BytesIO(png_data))
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    width, height = img.size

    # Encode as lossless WebP
    webp_buf = io.BytesIO()
    img.save(webp_buf, format="WEBP", lossless=True)
    webp_data = webp_buf.getvalue()

    # Build ctex header (56 bytes) + webp data
    header = bytearray()
    header += CTEX_MAGIC
    header += struct.pack("<I", CTEX_VERSION)
    header += struct.pack("<I", width)
    header += struct.pack("<I", height)
    header += struct.pack("<I", CTEX_FLAGS)
    header += struct.pack("<i", -1)  # limiter
    header += b"\x00" * 12  # padding
    header += struct.pack("<I", CTEX_DATA_FORMAT)
    header += struct.pack("<I", (height << 16) | width)  # packed dimensions
    header += struct.pack("<I", 0)  # padding
    header += struct.pack("<I", CTEX_IMAGE_FORMAT)
    header += struct.pack("<I", len(webp_data))

    assert len(header) == 56
    return bytes(header) + webp_data


def pack(source_dir: str, output_path: str, res_prefix: str):
    source = Path(source_dir)
    files: list[tuple[str, bytes]] = []

    for f in sorted(source.rglob("*")):
        if f.is_file():
            rel = f.relative_to(source)
            if f.suffix.lower() == ".png":
                # Convert PNG to ctex, store under .godot/imported/ path
                ctex_name = f"{f.stem}.png-imported.ctex"
                res_path = f"res://.godot/imported/{ctex_name}"
                ctex_data = png_to_ctex(f.read_bytes())
                files.append((res_path, ctex_data))
                # Also create the .import remap so Godot finds it
                import_remap = _make_import_remap(
                    f"res://{res_prefix}/{rel}",
                    res_path,
                )
                files.append((f"res://{res_prefix}/{rel}.import", import_remap))
                print(f"  PNG → ctex: {rel} ({len(ctex_data)} bytes)")
            else:
                res_path = f"res://{res_prefix}/{rel}"
                files.append((res_path, f.read_bytes()))
                print(f"  passthrough: {rel}")

    # Calculate header size
    header_size = 4 + 4 + 4 + 4 + 4 + 4 + 8 + 8 + (RESERVED_COUNT * 4)
    files_base = header_size

    # Pre-calculate file data layout
    file_entries: list[tuple[str, int, int, bytes]] = []
    data_offset = 0
    file_data_parts: list[tuple[int, bytes]] = []

    for res_path, data in files:
        pad = align(files_base + data_offset)
        data_offset += pad
        md5 = hashlib.md5(data).digest()
        file_entries.append((res_path, data_offset, len(data), md5))
        file_data_parts.append((pad, data))
        data_offset += len(data)

    dir_offset = files_base + data_offset

    # Build binary
    out = bytearray()

    # Header
    out += MAGIC
    out += struct.pack("<I", FORMAT_VERSION)
    out += struct.pack("<I", ENGINE_MAJOR)
    out += struct.pack("<I", ENGINE_MINOR)
    out += struct.pack("<I", ENGINE_PATCH)
    out += struct.pack("<I", PACK_REL_FILEBASE)
    out += struct.pack("<q", files_base)
    out += struct.pack("<q", dir_offset)
    out += b"\x00" * (RESERVED_COUNT * 4)

    assert len(out) == files_base

    # File data
    for pad, data in file_data_parts:
        out += b"\x00" * pad
        out += data

    assert len(out) == dir_offset

    # Directory index
    out += struct.pack("<I", len(file_entries))
    for res_path, offset, size, md5 in file_entries:
        path_bytes = res_path.encode("utf-8")
        padded_len = len(path_bytes)
        pad = align(padded_len, 4)
        padded_len += pad

        out += struct.pack("<I", padded_len)
        out += path_bytes
        out += b"\x00" * pad
        out += struct.pack("<q", offset)
        out += struct.pack("<q", size)
        out += md5
        out += struct.pack("<I", 0)  # flags

    Path(output_path).write_bytes(out)
    print(f"\nPacked {len(file_entries)} files into {output_path}")


def _make_import_remap(source_path: str, ctex_path: str) -> bytes:
    """Create a Godot .import file that remaps a PNG to its imported ctex."""
    content = f"""[remap]

importer="texture"
type="CompressedTexture2D"
path="{ctex_path}"
metadata={{
"vram_texture": false
}}

[deps]

source_file="{source_path}"
dest_files=["{ctex_path}"]

[params]

compress/mode=0
compress/high_quality=false
compress/lossy_quality=1.0
mipmaps/generate=false
"""
    return content.encode("utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <source_dir> <output.pck> <res_prefix>")
        sys.exit(1)
    pack(sys.argv[1], sys.argv[2], sys.argv[3])
