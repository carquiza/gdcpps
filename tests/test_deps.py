"""Tests for dependency sync ref resolution against local git repos."""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import deps


def _git(args, cwd=None):
    completed = subprocess.run(
        [
            "git",
            "-c", "user.email=ci@test",
            "-c", "user.name=ci",
            "-c", "protocol.file.allow=always",
            *args,
        ],
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


class ResolveSourceTests(unittest.TestCase):
    def test_none_uses_default(self):
        self.assertEqual(deps._resolve_source(None, "https://example.com/x.git"), "https://example.com/x.git")

    def test_existing_path_is_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(deps._resolve_source(tmp, "https://x"), str(Path(tmp).resolve()))

    def test_url_passes_through(self):
        url = "https://example.com/other.git"
        self.assertEqual(deps._resolve_source(url, "https://x"), url)


class CheckoutRefTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)

        self.src = root / "src"
        self.src.mkdir()
        _git(["init", "-q", "-b", "4.5", "."], cwd=self.src)
        _git(["commit", "-q", "--allow-empty", "-m", "A"], cwd=self.src)

        self.tgt = root / "tgt"
        _git(["clone", "-q", str(self.src), str(self.tgt)])

    def _head(self, repo):
        return _git(["rev-parse", "HEAD"], cwd=repo)

    def test_branch_resync_picks_up_new_commits(self):
        _git(["commit", "-q", "--allow-empty", "-m", "B"], cwd=self.src)
        _git(["fetch", "-q", "origin"], cwd=self.tgt)

        resolved = deps._checkout_ref(self.tgt, "4.5", [])

        self.assertEqual(resolved, "origin/4.5")
        self.assertEqual(self._head(self.tgt), self._head(self.src))

    def test_tag_ref_resolves(self):
        _git(["tag", "4.5.1-stable"], cwd=self.src)
        _git(["fetch", "-q", "--tags", "origin"], cwd=self.tgt)

        resolved = deps._checkout_ref(self.tgt, "4.5.1-stable", [])

        self.assertEqual(resolved, "4.5.1-stable")
        self.assertEqual(self._head(self.tgt), self._head(self.src))

    def test_stable_suffix_candidates(self):
        _git(["tag", "godot-9.9-stable"], cwd=self.src)
        _git(["fetch", "-q", "--tags", "origin"], cwd=self.tgt)

        resolved = deps._checkout_ref(self.tgt, "9.9", [])

        self.assertEqual(resolved, "godot-9.9-stable")

    def test_missing_ref_raises(self):
        with self.assertRaises(ValueError):
            deps._checkout_ref(self.tgt, "does-not-exist", [])


class EnvSourceResolutionTests(unittest.TestCase):
    def _project(self, tmp):
        proj = Path(tmp) / "p"
        proj.mkdir()
        (proj / "gdcpps.yaml").write_text("project:\n  name: p\n", encoding="utf-8")
        return proj

    def _run_capturing_sources(self, project, env, **flags):
        captured = {}

        def fake_sync(name, spec, target_root, source_override):
            captured[name] = source_override
            return {"path": "x", "source": "y", "ref": spec["ref"], "revision": "z"}

        with mock.patch.object(deps, "_sync_repo", fake_sync), mock.patch.object(
            deps, "_write_state", lambda *a, **k: None
        ), mock.patch.dict(os.environ, env, clear=False), redirect_stdout(io.StringIO()):
            deps.run(str(project), **flags)
        return captured

    def test_env_vars_used_when_flags_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            captured = self._run_capturing_sources(
                self._project(tmp),
                {"GODOT_SOURCE": "/env/godot", "GODOT_CPP_SOURCE": "/env/gdcpp"},
            )
            self.assertEqual(captured["godot"], "/env/godot")
            self.assertEqual(captured["godot_cpp"], "/env/gdcpp")

    def test_flag_overrides_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            captured = self._run_capturing_sources(
                self._project(tmp),
                {"GODOT_SOURCE": "/env/godot"},
                godot_source="/flag/godot",
            )
            self.assertEqual(captured["godot"], "/flag/godot")


if __name__ == "__main__":
    unittest.main()
