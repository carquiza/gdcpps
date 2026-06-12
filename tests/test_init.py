"""Tests for project scaffolding."""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import init


class ValidateProjectNameTests(unittest.TestCase):
    def test_valid_names(self):
        for name in ("my_game", "a", "game2", "abc_def_3"):
            init._validate_project_name(name)

    def test_invalid_names(self):
        for name in ("MyGame", "1abc", "my-game", "_x", "", "my game"):
            with self.assertRaises(ValueError, msg=name):
                init._validate_project_name(name)


class InitRunTests(unittest.TestCase):
    def test_creates_scaffold(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "proj"
            with redirect_stdout(io.StringIO()):
                rc = init.run("my_game", str(dest))
            self.assertEqual(rc, 0)

            manifest = (dest / "gdcpps.yaml").read_text(encoding="utf-8")
            self.assertIn("name: my_game", manifest)
            self.assertIn("module_name: my_game", manifest)

            header = (dest / "game" / "src" / "my_game_main.h").read_text(encoding="utf-8")
            self.assertIn("class MyGameMain", header)

            register = (dest / "game" / "register_types.cpp").read_text(encoding="utf-8")
            self.assertIn("my_game_library_init", register)

            for rel in (
                "README.md",
                ".gitignore",
                "gdcpps.bat",
                "gdcpps.sh",
                "project/project.godot",
                "project/main.tscn",
                "project/bin/my_game.gdextension",
                "game/include/gdcpp.h",
                "game/src/my_game_main.cpp",
                "module/config.py",
                "module/SCsub",
                "module/register_types.cpp",
            ):
                self.assertTrue((dest / rel).is_file(), rel)

            for directory in ("build", "deps", "artifacts"):
                self.assertTrue((dest / directory).is_dir(), directory)

    def test_existing_destination_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "proj"
            dest.mkdir()
            with self.assertRaises(FileExistsError):
                init.run("my_game", str(dest))

    def test_invalid_name_raises_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "proj"
            with self.assertRaises(ValueError):
                init.run("Bad-Name", str(dest))
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
