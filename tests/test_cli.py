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
import run as run_cmd
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

    def test_run_forwards_extra_args(self):
        args = self.parser.parse_args(
            ["run", "--project", "p", "debug", "windows", "--", "--screenshot", "out.png"]
        )
        self.assertEqual(args.project_dir, "p")
        # argparse keeps or strips the leading "--" depending on Python
        # version; _game_args normalizes both forms.
        self.assertEqual(run_cmd._game_args(args.extra_args), ["--screenshot", "out.png"])

    def test_run_without_extra_args(self):
        args = self.parser.parse_args(["run", "debug", "windows"])
        self.assertEqual(args.extra_args, [])


class GameArgsTests(unittest.TestCase):
    def test_strips_leading_separator(self):
        self.assertEqual(run_cmd._game_args(["--", "--screenshot", "x.png"]), ["--screenshot", "x.png"])

    def test_no_separator_passthrough(self):
        self.assertEqual(run_cmd._game_args(["--fullscreen"]), ["--fullscreen"])

    def test_none_and_empty(self):
        self.assertEqual(run_cmd._game_args(None), [])
        self.assertEqual(run_cmd._game_args([]), [])


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


class RunDebugSelfHealTests(unittest.TestCase):
    """`run debug` must restore .godot/extension_list.cfg regardless of the last
    build. A prior `release` build deletes it (release links the module into the
    engine and must not also load the GDExtension), which otherwise leaves debug
    runs unable to register the extension's classes."""

    def _make_project(self, root: Path, module_name: str, platform: str) -> Path:
        project = root / "proj"
        (project).mkdir()
        (project / "gdcpps.yaml").write_text(
            f"project:\n  module_name: {module_name}\n", encoding="utf-8"
        )
        bin_dir = project / "project" / "bin"
        bin_dir.mkdir(parents=True)
        # Debug artifact present (as after `build debug`); only the runtime cfg is gone.
        (bin_dir / f"lib{module_name}.{platform}.template_debug.universal.dylib").write_text(
            "", encoding="utf-8"
        )
        return project

    def test_regenerates_missing_extension_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp), "my_game", "macos")
            extension_list = project / "project" / ".godot" / "extension_list.cfg"
            self.assertFalse(extension_list.exists())

            with mock.patch.object(run_cmd, "_resolve_godot_bin", return_value="godot"), \
                    mock.patch.object(run_cmd.subprocess, "run") as run_mock:
                rc = run_cmd.run(str(project), "debug", "macos")

            self.assertEqual(rc, 0)
            run_mock.assert_called_once()
            self.assertTrue(extension_list.exists())
            self.assertEqual(
                extension_list.read_text(encoding="utf-8"),
                "res://bin/my_game.gdextension\n",
            )


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
