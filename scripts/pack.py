"""Packs project files into a Godot .pck and optionally embeds it into an executable."""

from __future__ import annotations

import hashlib
import os
import struct
import sys


PACK_HEADER_MAGIC = 0x43504447
PACK_FORMAT_VERSION = 3
PACK_ALIGNMENT = 64
PACK_REL_FILEBASE = 1 << 1
ALLOWED_PROJECT_DATA_FILES = {
    ".godot/global_script_class_cache.cfg",
}
IGNORED_PACK_FILES = {
    "gdcpp_log.txt",
}


def pad_to(n: int, alignment: int) -> int:
    remainder = n % alignment
    if remainder == 0:
        return 0
    return alignment - remainder


def collect_files(project_dir: str) -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    for root, dirs, filenames in os.walk(project_dir):
        rel_root = os.path.relpath(root, project_dir).replace("\\", "/")

        dirs[:] = [directory for directory in dirs if directory != "bin"]

        if rel_root == ".godot":
            dirs[:] = []
        elif rel_root.startswith(".godot/"):
            dirs[:] = []
            continue

        for fname in filenames:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, project_dir).replace("\\", "/")
            if fname in IGNORED_PACK_FILES:
                continue
            if rel_path.startswith(".godot/") and rel_path not in ALLOWED_PROJECT_DATA_FILES:
                continue
            files.append((rel_path, full_path))
    return sorted(files)


def write_pck(project_dir: str, output_path: str) -> str:
    files = collect_files(project_dir)
    print(f"Packing {len(files)} files from {project_dir}")

    with open(output_path, "wb") as handle:
        handle.write(struct.pack("<I", PACK_HEADER_MAGIC))
        handle.write(struct.pack("<I", PACK_FORMAT_VERSION))
        handle.write(struct.pack("<III", 4, 5, 1))
        handle.write(struct.pack("<I", PACK_REL_FILEBASE))

        file_base_pos = handle.tell()
        handle.write(struct.pack("<Q", 0))

        dir_offset_pos = handle.tell()
        handle.write(struct.pack("<Q", 0))

        handle.write(b"\x00" * 64)

        padding = pad_to(handle.tell(), PACK_ALIGNMENT)
        handle.write(b"\x00" * padding)
        file_base = handle.tell()

        handle.seek(file_base_pos)
        handle.write(struct.pack("<Q", file_base))
        handle.seek(file_base)

        file_entries = []
        for pack_path, full_path in files:
            padding = pad_to(handle.tell(), PACK_ALIGNMENT)
            handle.write(b"\x00" * padding)

            offset = handle.tell()
            with open(full_path, "rb") as source:
                data = source.read()

            md5 = hashlib.md5(data).digest()
            handle.write(data)
            file_entries.append((pack_path, offset - file_base, len(data), md5))

        padding = pad_to(handle.tell(), PACK_ALIGNMENT)
        handle.write(b"\x00" * padding)
        dir_offset = handle.tell()

        handle.seek(dir_offset_pos)
        handle.write(struct.pack("<Q", dir_offset))
        handle.seek(dir_offset)

        handle.write(struct.pack("<I", len(file_entries)))

        for pack_path, offset, size, md5 in file_entries:
            path_bytes = pack_path.encode("utf-8")
            path_pad = pad_to(len(path_bytes), 4)

            handle.write(struct.pack("<I", len(path_bytes) + path_pad))
            handle.write(path_bytes)
            handle.write(b"\x00" * path_pad)
            handle.write(struct.pack("<Q", offset))
            handle.write(struct.pack("<Q", size))
            handle.write(md5)
            handle.write(struct.pack("<I", 0))

    print(f"Wrote {output_path} ({os.path.getsize(output_path)} bytes)")
    return output_path


def embed_pck(exe_path: str, pck_path: str) -> None:
    with open(pck_path, "rb") as source:
        pck_data = source.read()

    exe_size = os.path.getsize(exe_path)

    with open(exe_path, "ab") as handle:
        padding = pad_to(exe_size, 8)
        handle.write(b"\x00" * padding)

        pck_start = handle.tell()
        handle.write(pck_data)

        embedded_pck_size = handle.tell() - pck_start
        handle.write(struct.pack("<Q", embedded_pck_size))
        handle.write(struct.pack("<I", PACK_HEADER_MAGIC))

    print(f"Embedded PCK into {exe_path} (final size: {os.path.getsize(exe_path)} bytes)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: pack.py <project_dir> <output.pck> [--embed <executable>]")
        raise SystemExit(1)

    project_dir = sys.argv[1]
    pck_path = sys.argv[2]

    write_pck(project_dir, pck_path)

    if len(sys.argv) >= 5 and sys.argv[3] == "--embed":
        embed_pck(sys.argv[4], pck_path)
        os.remove(pck_path)
        print("Removed standalone .pck (embedded into exe)")
