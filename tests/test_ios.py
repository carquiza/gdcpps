"""Tests for ios.py helpers (no engine build, editor or Xcode required)."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ios

EXPORT = {"bundle_id": "com.example.game", "team_id": "ABCDE12345", "min_ios_version": "15.0"}


class ExportConfigTests(unittest.TestCase):
    def test_requires_bundle_and_team(self):
        with self.assertRaises(ValueError):
            ios.export_config({"platforms": {"ios": {"export": {"bundle_id": "a.b"}}}})

    def test_defaults(self):
        cfg = ios.export_config({"project": {"name": "mygame"}, "platforms": {"ios": {"export": dict(EXPORT)}}})
        self.assertEqual(cfg["display_name"], "mygame")
        self.assertEqual(cfg["min_ios_version"], "15.0")


class ExportPresetTests(unittest.TestCase):
    def test_creates_preset(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            ios.write_export_preset(project, Path("/t/godot_ios.zip"), EXPORT, "../out/game.ipa", Path("/i/icon.png"))
            text = (project / "export_presets.cfg").read_text()
            self.assertIn("[preset.0]", text)
            self.assertIn('name="iOS"', text)
            self.assertIn('include_filter=""', text)
            self.assertIn('custom_template/release="/t/godot_ios.zip"', text)
            self.assertIn('application/bundle_identifier="com.example.game"', text)
            self.assertIn('icons/icon_1024x1024="/i/icon.png"', text)

    def test_updates_managed_keys_and_keeps_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "export_presets.cfg").write_text(
                '[preset.0]\n\nname="Web"\nplatform="Web"\n\n[preset.0.options]\n\nhtml/x=1\n\n'
                '[preset.1]\n\nname="iOS"\nplatform="iOS"\ninclude_filter="*.json"\n\n'
                '[preset.1.options]\n\napplication/version="2.0"\ncustom_template/release="/old.zip"\n'
            )
            ios.write_export_preset(project, Path("/new.zip"), EXPORT, "out.ipa", None)
            text = (project / "export_presets.cfg").read_text()
            self.assertIn('name="Web"', text)
            self.assertIn("html/x=1", text)
            self.assertIn('include_filter="*.json"', text)  # not overwritten
            self.assertIn('application/version="2.0"', text)
            self.assertIn('custom_template/release="/new.zip"', text)
            self.assertNotIn("/old.zip", text)
            self.assertNotIn("[preset.2]", text)


class TemplateTests(unittest.TestCase):
    def test_strip_moltenvk(self):
        with tempfile.TemporaryDirectory() as tmp:
            pbx = Path(tmp) / "project.pbxproj"
            pbx.write_text("a\n\t\t9039 /* MoltenVK.xcframework in Frameworks */ = {};\nb\n")
            ios._strip_moltenvk(pbx)
            self.assertEqual(pbx.read_text(), "a\nb\n")


if __name__ == "__main__":
    unittest.main()
