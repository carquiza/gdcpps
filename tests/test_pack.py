"""Tests for pack.py PCK writing and embedding."""

import hashlib
import io
import json
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pack


def _parse_pck(path):
    data = Path(path).read_bytes()
    magic, fmt, major, minor, patch, flags, file_base, dir_offset = struct.unpack_from("<6I2Q", data, 0)

    (count,) = struct.unpack_from("<I", data, dir_offset)
    pos = dir_offset + 4
    entries = {}
    for _ in range(count):
        (path_len,) = struct.unpack_from("<I", data, pos)
        pos += 4
        name = data[pos : pos + path_len].rstrip(b"\x00").decode("utf-8")
        pos += path_len
        offset, size = struct.unpack_from("<2Q", data, pos)
        pos += 16
        md5 = data[pos : pos + 16]
        pos += 16
        (entry_flags,) = struct.unpack_from("<I", data, pos)
        pos += 4
        entries[name] = {"offset": offset, "size": size, "md5": md5, "flags": entry_flags}

    header = {
        "magic": magic,
        "format": fmt,
        "version": (major, minor, patch),
        "flags": flags,
        "file_base": file_base,
    }
    return header, entries, data


class PadToTests(unittest.TestCase):
    def test_aligned_needs_no_padding(self):
        self.assertEqual(pack.pad_to(0, 64), 0)
        self.assertEqual(pack.pad_to(64, 64), 0)

    def test_unaligned_padding(self):
        self.assertEqual(pack.pad_to(1, 64), 63)
        self.assertEqual(pack.pad_to(63, 64), 1)
        self.assertEqual(pack.pad_to(13, 8), 3)


class GodotVersionTests(unittest.TestCase):
    def test_matches_versions_json(self):
        versions_path = Path(__file__).resolve().parents[1] / "versions.json"
        version = json.loads(versions_path.read_text(encoding="utf-8"))["godot"]["version"]
        expected = [int(part) for part in str(version).split(".")[:3]]
        while len(expected) < 3:
            expected.append(0)
        self.assertEqual(pack._godot_version_tuple(), tuple(expected))


class CollectFilesTests(unittest.TestCase):
    def test_filters_runtime_and_cache_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.tscn").write_text("scene", encoding="utf-8")
            (root / "assets").mkdir()
            (root / "assets" / "tex.png").write_bytes(b"png")
            (root / "bin").mkdir()
            (root / "bin" / "lib.dll").write_bytes(b"dll")
            (root / ".godot").mkdir()
            (root / ".godot" / "global_script_class_cache.cfg").write_text("[]", encoding="utf-8")
            (root / ".godot" / "uid_cache.bin").write_bytes(b"uid")
            (root / ".godot" / "imported").mkdir()
            (root / ".godot" / "imported" / "x.ctex").write_bytes(b"x")
            (root / "gdcpp_log.txt").write_text("log", encoding="utf-8")

            rel_paths = [rel for rel, _ in pack.collect_files(str(root))]

        self.assertIn("main.tscn", rel_paths)
        self.assertIn("assets/tex.png", rel_paths)
        self.assertIn(".godot/global_script_class_cache.cfg", rel_paths)
        self.assertNotIn("bin/lib.dll", rel_paths)
        self.assertNotIn(".godot/uid_cache.bin", rel_paths)
        self.assertNotIn(".godot/imported/x.ctex", rel_paths)
        self.assertNotIn("gdcpp_log.txt", rel_paths)
        self.assertEqual(rel_paths, sorted(rel_paths))


class WritePckTests(unittest.TestCase):
    def test_roundtrip(self):
        contents = {
            "a.txt": b"alpha",
            "sub/b.bin": b"\x00\x01\x02" * 100,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proj = root / "proj"
            (proj / "sub").mkdir(parents=True)
            for rel, data in contents.items():
                (proj / rel).write_bytes(data)

            out = root / "out.pck"
            with redirect_stdout(io.StringIO()):
                pack.write_pck(str(proj), str(out))
            header, entries, data = _parse_pck(out)

        self.assertEqual(header["magic"], pack.PACK_HEADER_MAGIC)
        self.assertEqual(header["format"], pack.PACK_FORMAT_VERSION)
        self.assertEqual(header["flags"], pack.PACK_REL_FILEBASE)
        self.assertEqual(header["version"], pack._godot_version_tuple())
        self.assertEqual(set(entries), set(contents))

        for rel, expected in contents.items():
            entry = entries[rel]
            start = header["file_base"] + entry["offset"]
            self.assertEqual(start % pack.PACK_ALIGNMENT, 0, rel)
            self.assertEqual(data[start : start + entry["size"]], expected, rel)
            self.assertEqual(entry["md5"], hashlib.md5(expected).digest(), rel)
            self.assertEqual(entry["flags"], 0, rel)


class EmbedPckTests(unittest.TestCase):
    def test_embed_appends_pck_with_trailer(self):
        exe_bytes = b"EXEBYTES12345"  # 13 bytes, exercises 8-byte padding
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "game.exe"
            exe.write_bytes(exe_bytes)
            proj = root / "proj"
            proj.mkdir()
            (proj / "a.txt").write_text("a", encoding="utf-8")

            pck = root / "x.pck"
            with redirect_stdout(io.StringIO()):
                pack.write_pck(str(proj), str(pck))
                pck_bytes = pck.read_bytes()
                pack.embed_pck(str(exe), str(pck))
            data = exe.read_bytes()

        pck_start = len(exe_bytes) + pack.pad_to(len(exe_bytes), 8)
        self.assertEqual(data[: len(exe_bytes)], exe_bytes)
        self.assertEqual(data[pck_start : pck_start + len(pck_bytes)], pck_bytes)
        (embedded_size,) = struct.unpack_from("<Q", data, len(data) - 12)
        self.assertEqual(embedded_size, len(pck_bytes))
        (magic,) = struct.unpack_from("<I", data, len(data) - 4)
        self.assertEqual(magic, pack.PACK_HEADER_MAGIC)


if __name__ == "__main__":
    unittest.main()
