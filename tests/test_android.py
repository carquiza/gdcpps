"""Tests for android.py helpers (no engine build, editor, gradle or device required)."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import android


class ExportConfigTests(unittest.TestCase):
    def test_requires_package(self):
        with self.assertRaises(ValueError):
            android.export_config({"platforms": {"android": {"export": {}}}})

    def test_display_name_default(self):
        cfg = android.export_config({"project": {"name": "mygame"}, "platforms": {"android": {"export": {"package": "a.b"}}}})
        self.assertEqual(cfg["display_name"], "mygame")


class SigningTests(unittest.TestCase):
    def test_custom_keystore_needs_password_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "release.jks").write_text("x")
            export = {"package": "a.b", "keystore": "release.jks", "keystore_user": "me", "keystore_password_env": "GDCPPS_TEST_PW"}
            with mock.patch.dict("os.environ", {}, clear=False):
                with self.assertRaises(ValueError):
                    android._signing(root, export)
            with mock.patch.dict("os.environ", {"GDCPPS_TEST_PW": "secret"}):
                keystore, alias, password = android._signing(root, export)
            self.assertEqual((keystore.name, alias, password), ("release.jks", "me", "secret"))


class DeviceTests(unittest.TestCase):
    def _devices(self, text):
        result = mock.Mock(stdout=text)
        return mock.patch.object(android.subprocess, "run", return_value=result)

    def test_single_device(self):
        with self._devices("List of devices attached\nR58N123\tdevice\n\n"):
            self.assertEqual(android._pick_device("adb", None), "R58N123")

    def test_none_or_unauthorized(self):
        with self._devices("List of devices attached\nR58N123\tunauthorized\n"):
            with self.assertRaises(RuntimeError):
                android._pick_device("adb", None)

    def test_several_need_a_choice(self):
        with self._devices("List of devices attached\nA\tdevice\nB\tdevice\n"):
            with self.assertRaises(RuntimeError):
                android._pick_device("adb", None)
            self.assertEqual(android._pick_device("adb", "B"), "B")


if __name__ == "__main__":
    unittest.main()
