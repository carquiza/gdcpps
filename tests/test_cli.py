"""Tests for the CLI parser and dispatch, plus doctor and toolchain helpers."""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import doctor
import gdcpps
import toolchains


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = gdcpps.build_parser()

    def test_deps_sync_defaults_to_current_directory(self):
        args = self.parser.parse_args(["deps", "sync"])
        self.assertEqual(args.project_dir, ".")

    def test_deps_sync_accepts_project_dir(self):
        args = self.parser.parse_args(["deps", "sync", "some/project"])
        self.assertEqual(args.project_dir, "some/project")

    def test_build_defaults_to_current_directory(self):
        args = self.parser.parse_args(["build", "debug", "windows"])
        self.assertEqual(args.project_dir, ".")
        self.assertEqual(args.mode, "debug")
        self.assertEqual(args.platform, "windows")


class MainTests(unittest.TestCase):
    def test_no_command_prints_help_and_returns_1(self):
        with redirect_stdout(io.StringIO()) as buf:
            rc = gdcpps.main([])
        self.assertEqual(rc, 1)
        self.assertIn("usage:", buf.getvalue())

    def test_doctor_returns_0(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(gdcpps.main(["doctor"]), 0)

    def test_command_errors_are_reported_not_raised(self):
        with redirect_stdout(io.StringIO()) as buf:
            rc = gdcpps.main(["build", "bogus-mode", "windows"])
        self.assertEqual(rc, 1)
        self.assertIn("error:", buf.getvalue())


class DoctorTests(unittest.TestCase):
    def test_run_reports_and_returns_zero(self):
        with redirect_stdout(io.StringIO()) as buf:
            rc = doctor.run()
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("Tools", out)
        self.assertIn("Environment", out)
        self.assertIn("pyyaml", out)


class ToolchainsTests(unittest.TestCase):
    def _make_fake_emsdk(self, root: Path) -> Path:
        emsdk = root / "emsdk"
        emcc_name = "emcc.bat" if os.name == "nt" else "emcc"
        emcc = emsdk / "upstream" / "emscripten" / emcc_name
        emcc.parent.mkdir(parents=True)
        emcc.write_text("", encoding="utf-8")
        return emsdk

    def test_find_emsdk_root_from_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            emsdk = self._make_fake_emsdk(Path(tmp))
            with mock.patch.dict(os.environ, {"EMSDK": str(emsdk)}):
                self.assertEqual(toolchains.find_emsdk_root(), emsdk.resolve())

    def test_emsdk_env_prepends_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            emsdk = self._make_fake_emsdk(Path(tmp))
            with mock.patch.dict(os.environ, {"EMSDK": str(emsdk)}):
                env = toolchains.emsdk_env()
        self.assertIsNotNone(env)
        resolved = emsdk.resolve()
        self.assertEqual(env["EMSDK"], str(resolved))
        self.assertEqual(env["EM_CONFIG"], str(resolved / ".emscripten"))
        first_entry = env["PATH"].split(os.pathsep)[0]
        self.assertEqual(first_entry, str(resolved / "upstream" / "emscripten"))


if __name__ == "__main__":
    unittest.main()
