"""Tests for upgrading existing gdcpps projects."""

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import init
import upgrade

HAS_YAML = importlib.util.find_spec("yaml") is not None


@unittest.skipUnless(HAS_YAML, "PyYAML not installed")


def _scaffold(tmp: str, name: str = "my_game") -> Path:
    dest = Path(tmp) / "proj"
    with redirect_stdout(io.StringIO()):
        init.run(name, str(dest))
    return dest


class UpgradeRunTests(unittest.TestCase):
    def test_refreshes_infrastructure_and_keeps_user_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _scaffold(tmp)

            # Mark an infrastructure file (always overwritten) and a user-owned
            # file (only created if missing) to observe what upgrade touches.
            launcher = dest / "gdcpps.sh"
            launcher.write_text("stale launcher\n", encoding="utf-8")
            manifest = dest / "gdcpps.yaml"
            manifest_before = manifest.read_text(encoding="utf-8")

            with redirect_stdout(io.StringIO()):
                rc = upgrade.run(str(dest))
            self.assertEqual(rc, 0)

            # Infrastructure is force-rewritten back to the current template.
            self.assertNotEqual(launcher.read_text(encoding="utf-8"), "stale launcher\n")
            self.assertTrue((dest / "module" / "SCsub").is_file())

            # User-owned files are left untouched.
            self.assertEqual(manifest.read_text(encoding="utf-8"), manifest_before)

            for directory in ("build", "deps", "artifacts"):
                self.assertTrue((dest / directory).is_dir(), directory)

    def test_survives_manifest_without_project_name(self):
        # Older / hand-edited manifests may omit project.name; upgrade should
        # still succeed rather than raising KeyError.
        with tempfile.TemporaryDirectory() as tmp:
            dest = _scaffold(tmp)
            (dest / "gdcpps.yaml").write_text(
                "project:\n  module_name: my_game\n", encoding="utf-8"
            )

            with redirect_stdout(io.StringIO()):
                rc = upgrade.run(str(dest))
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
