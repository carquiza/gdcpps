"""Tests for build.py helpers (no engine build required)."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build


class StringListTests(unittest.TestCase):
    def test_non_list_is_empty(self):
        self.assertEqual(build._string_list(None), [])
        self.assertEqual(build._string_list("text"), [])
        self.assertEqual(build._string_list({"a": 1}), [])

    def test_dedupes_preserving_order(self):
        self.assertEqual(build._string_list(["b", "a", "b", "c", "a"]), ["b", "a", "c"])

    def test_skips_non_strings_and_empties(self):
        self.assertEqual(build._string_list(["a", "", None, 3, "b"]), ["a", "b"])

    def test_merge_order_and_dedupe(self):
        merged = build._merge_string_lists(["a", "b"], None, ["b", "c"], ["a", "d"])
        self.assertEqual(merged, ["a", "b", "c", "d"])


class ResolveManifestPathsTests(unittest.TestCase):
    def test_relative_paths_resolve_from_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = build._resolve_manifest_paths(root, ["inc", "../shared"])
            self.assertEqual(resolved[0], (root / "inc").resolve())
            self.assertEqual(resolved[1], (root / ".." / "shared").resolve())

    def test_absolute_paths_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            absolute = (root / "abs").resolve()
            resolved = build._resolve_manifest_paths(root / "proj", [str(absolute)])
            self.assertEqual(resolved, [absolute])

    def test_non_list_is_empty(self):
        self.assertEqual(build._resolve_manifest_paths(Path("."), "inc"), [])


class BuildExtensionsTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "build": {
                "cpp_standard": "c++20",
                "shared": {"extra_include_dirs": ["inc_shared"], "defines": ["A"]},
                "debug": {"include_dirs": ["inc_debug"], "cxxflags": ["-g"]},
                "module": {"extra_include_dirs": ["inc_module"]},
            },
            "platforms": {
                "windows": {
                    "build": {
                        "shared": {"defines": ["B"]},
                        "debug": {"extra_source_globs": ["win/*.cpp"]},
                    }
                }
            },
        }

    def test_merges_shared_mode_and_platform_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ext = build._build_extensions(root, self.manifest, "debug", "windows")

            self.assertEqual(ext["cpp_standard"], "c++20")
            self.assertEqual(
                ext["include_dirs"],
                [(root / "inc_shared").resolve(), (root / "inc_debug").resolve()],
            )
            self.assertEqual(ext["source_globs"], [(root / "win" / "*.cpp").resolve()])
            self.assertEqual(ext["defines"], ["A", "B"])
            self.assertEqual(ext["cxxflags"], ["-g"])

    def test_mode_sections_do_not_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ext = build._build_extensions(root, self.manifest, "module", "linux")

            self.assertEqual(
                ext["include_dirs"],
                [(root / "inc_shared").resolve(), (root / "inc_module").resolve()],
            )
            self.assertEqual(ext["defines"], ["A"])
            self.assertEqual(ext["cxxflags"], [])

    def test_no_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ext = build._build_extensions(root, self.manifest, "debug", None)
            self.assertEqual(ext["defines"], ["A"])


class RenderHelpersTests(unittest.TestCase):
    def test_python_string_list(self):
        self.assertEqual(build._python_string_list([]), "[]")
        self.assertEqual(build._python_string_list(["a", "b"]), "['a', 'b']")

    def test_python_path_list(self):
        self.assertEqual(build._python_path_list([]), "[]")
        rendered = build._python_path_list([Path("/x/y")])
        self.assertTrue(rendered.startswith('[r"'))
        self.assertIn("y", rendered)

    def test_scons_flag_block_sets_std_and_flags(self):
        block = build._scons_flag_block(
            "env", {"cpp_standard": "c++20", "cxxflags": ["-fno-exceptions"]}
        )
        self.assertIn('/std:c++20', block)
        self.assertIn('-std=c++20', block)
        self.assertIn('env.Append(CXXFLAGS=[\'-fno-exceptions\'])', block)

    def test_scons_flag_block_empty(self):
        self.assertEqual(build._scons_flag_block("env", {"cpp_standard": None, "cxxflags": []}), "")

    def test_gdextension_text_covers_platforms(self):
        text = build._gdextension_text("mymod")
        self.assertIn('entry_symbol = "mymod_library_init"', text)
        for platform in ("windows.debug.x86_64", "linux.release.arm64", "macos.debug", "web.release.wasm32"):
            self.assertIn(platform, text)


class RunValidationTests(unittest.TestCase):
    def test_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            build.run(".", "bogus", "windows")

    def test_rejects_unknown_platform(self):
        with self.assertRaises(ValueError):
            build.run(".", "debug", "solaris")

    def test_supported_platforms_include_macos(self):
        self.assertIn("macos", build.SUPPORTED_PLATFORMS)


if __name__ == "__main__":
    unittest.main()
