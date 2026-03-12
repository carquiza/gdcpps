"""Runtime helpers for gdcpps projects."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from profile_resolver import load_manifest


def _resolve_godot_bin() -> str:
    env_bin = os.environ.get("GODOT_BIN")
    if env_bin:
        return env_bin

    for candidate in ("godot", "godot4", "godot4.6"):
        path = shutil.which(candidate)
        if path:
            return path

    raise FileNotFoundError(
        "Debug runs require GODOT_BIN or a Godot executable on PATH."
    )


def _pick_release_executable(build_dir: Path) -> Path:
    candidates = [
        build_dir / "godot.windows.template_release.x86_64.exe",
        build_dir / "godot.windows.template_release.x86_64.console.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No Windows release executable found in {build_dir}")


def run(project_dir: str, mode: str, platform: str) -> int:
    project_root = Path(project_dir).resolve()
    manifest = load_manifest(project_root)
    project_name = str(manifest.get("project", {}).get("name", project_root.name))

    if platform != "windows":
        raise ValueError("`gdcpps run` currently supports the windows platform only.")

    if mode == "debug":
        project_path = project_root / "project"
        dlls = list((project_path / "bin").glob("*.windows.template_debug*.dll"))
        if not dlls:
            raise FileNotFoundError(
                f"No Windows debug GDExtension DLL found in {project_path / 'bin'}. Run `gdcpps build debug windows --project {project_root}` first."
            )

        cmd = [_resolve_godot_bin(), "--path", str(project_path)]
        print(f"Running debug project {project_name}: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        return 0

    if mode == "release":
        build_dir = project_root / "build" / "windows" / "release"
        exe_path = _pick_release_executable(build_dir)
        print(f"Running release project {project_name}: {exe_path}")
        subprocess.run([str(exe_path)], cwd=str(build_dir), check=True)
        return 0

    raise ValueError("`gdcpps run` currently supports debug and release modes only.")
