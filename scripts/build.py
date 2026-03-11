"""Build orchestration for gdcpps projects."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pack
from profile_resolver import load_manifest, render_profile, resolve_flags


SUPPORTED_PLATFORMS = {"windows", "web"}
SUPPORTED_MODES = {"debug", "release"}


def _load_deps_state(project_root: Path) -> dict:
    state_path = project_root / ".gdcpps" / "state" / "deps.json"
    if not state_path.exists():
        raise FileNotFoundError(
            f"Missing dependency state: {state_path}. Run `gdcpps deps sync {project_root}` first."
        )
    return json.loads(state_path.read_text(encoding="utf-8"))


def _project_module_name(manifest: dict) -> str:
    project = manifest.get("project", {})
    module_name = project.get("module_name")
    if not module_name:
        raise ValueError("Manifest is missing project.module_name")
    return str(module_name)


def _jobs() -> str:
    cpu_count = os.cpu_count() or 4
    return str(cpu_count)


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True)


def _ensure_project_runtime_files(project_root: Path, module_name: str, debug_mode: bool) -> None:
    godot_dir = project_root / "project" / ".godot"
    godot_dir.mkdir(parents=True, exist_ok=True)

    cache_path = godot_dir / "global_script_class_cache.cfg"
    if not cache_path.exists():
        cache_path.write_text('[""]\n\nlist=[]\n', encoding="utf-8", newline="\n")

    extension_list = godot_dir / "extension_list.cfg"
    if debug_mode:
        extension_list.write_text(
            f"res://bin/{module_name}.gdextension\n",
            encoding="utf-8",
            newline="\n",
        )
    elif extension_list.exists():
        extension_list.unlink()


def _write_debug_sconstruct(project_root: Path, godot_cpp_dir: Path, module_name: str) -> Path:
    upper_name = module_name.upper()
    content = f"""#!/usr/bin/env python
import os
from glob import glob

project_root = r"{project_root.resolve()}"
godot_cpp_dir = r"{godot_cpp_dir.resolve()}"
game_dir = os.path.join(project_root, "game")
project_dir = os.path.join(project_root, "project")

env = SConscript(os.path.join(godot_cpp_dir, "SConstruct"))
env.Append(CPPPATH=[os.path.join(game_dir, "include"), game_dir])
env.Append(CPPDEFINES=["{upper_name}_GDEXTENSION"])

sources = sorted(glob(os.path.join(game_dir, "src", "*.cpp")))
sources.append(os.path.join(game_dir, "register_types.cpp"))

library = env.SharedLibrary(
    os.path.join(project_dir, "bin", "lib{module_name}" + env["suffix"] + env["SHLIBSUFFIX"]),
    source=sources,
)

env.NoCache(library)
Default(library)
"""
    sconstruct_path = project_root / ".gdcpps" / "generated" / "SConstruct.debug"
    sconstruct_path.parent.mkdir(parents=True, exist_ok=True)
    sconstruct_path.write_text(content, encoding="utf-8", newline="\n")
    return sconstruct_path


def _copy_matches(pattern: str, destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for source in destination.parent.parent.parent.glob(pattern):
        target = destination / source.name
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def _copy_files(sources: list[Path], destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for source in sources:
        target = destination / source.name
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def _render_release_profile(project_root: Path, platform: str) -> Path:
    manifest = load_manifest(project_root)
    flags = resolve_flags(manifest, platform)
    profile_path = project_root / ".gdcpps" / "generated" / f"{platform}.profile.py"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(render_profile(flags), encoding="utf-8", newline="\n")
    return profile_path


def _build_output_dir(project_root: Path, platform: str, mode: str) -> Path:
    return project_root / "build" / platform / mode


def _build_debug(project_root: Path, platform: str, deps_state: dict, module_name: str) -> Path:
    godot_cpp_dir = Path(deps_state["dependencies"]["godot_cpp"]["path"])
    if not (godot_cpp_dir / "SConstruct").exists():
        raise FileNotFoundError(f"Missing godot-cpp SConstruct in {godot_cpp_dir}")

    if platform == "web" and shutil.which("emcc") is None:
        raise EnvironmentError("Web debug build requires emcc in PATH.")

    _ensure_project_runtime_files(project_root, module_name, debug_mode=True)
    sconstruct_path = _write_debug_sconstruct(project_root, godot_cpp_dir, module_name)

    cmd = [
        sys.executable,
        "-m",
        "SCons",
        "-f",
        str(sconstruct_path),
        f"platform={platform}",
        "target=template_debug",
        f"-j{_jobs()}",
    ]
    _run(cmd, project_root)

    project_bin = project_root / "project" / "bin"
    artifacts = list(project_bin.glob(f"lib{module_name}*"))
    if not artifacts:
        raise FileNotFoundError(f"No debug artifacts found in {project_bin}")

    destination = _build_output_dir(project_root, platform, "debug")
    _copy_files(artifacts, destination)
    return destination


def _copy_native_release_outputs(godot_dir: Path, destination: Path, platform: str) -> list[Path]:
    bin_dir = godot_dir / "bin"
    if platform == "windows":
        sources = list(bin_dir.glob("godot.windows.template_release*.exe"))
    elif platform == "web":
        sources = list(bin_dir.glob("godot.web.template_release*.wasm")) + list(
            bin_dir.glob("godot.web.template_release*.js")
        )
    else:
        raise ValueError(f"Unsupported platform: {platform}")

    if not sources:
        raise FileNotFoundError(f"No release artifacts found in {bin_dir} for {platform}")

    return _copy_files(sorted(sources), destination)


def _write_web_shell(destination: Path, base_name: str, title: str) -> None:
    template_path = Path(__file__).resolve().parent / "web_shell.html"
    html = template_path.read_text(encoding="utf-8")
    html = html.replace("__GODOT_JS__", base_name + ".js")
    html = html.replace("__GODOT_BASE__", base_name)
    html = html.replace("__TITLE__", title)
    (destination / "index.html").write_text(html, encoding="utf-8", newline="\n")


def _pack_windows_release(project_root: Path, build_dir: Path) -> None:
    temp_pck = build_dir / "temp.pck"
    project_dir = project_root / "project"

    for exe_path in sorted(build_dir.glob("godot.windows.template_release*.exe")):
        pack.write_pck(str(project_dir), str(temp_pck))
        pack.embed_pck(str(exe_path), str(temp_pck))
        temp_pck.unlink(missing_ok=True)


def _pack_web_release(project_root: Path, build_dir: Path, project_name: str) -> None:
    wasm_files = sorted(build_dir.glob("*.wasm"))
    if not wasm_files:
        raise FileNotFoundError(f"No wasm output found in {build_dir}")

    base_name = wasm_files[0].stem
    pck_path = build_dir / f"{base_name}.pck"
    pack.write_pck(str(project_root / "project"), str(pck_path))
    _write_web_shell(build_dir, base_name, project_name)


def _build_release(project_root: Path, platform: str, deps_state: dict, module_name: str, project_name: str) -> Path:
    godot_dir = Path(deps_state["dependencies"]["godot"]["path"])
    if not (godot_dir / "SConstruct").exists():
        raise FileNotFoundError(f"Missing Godot SConstruct in {godot_dir}")

    if platform == "web" and shutil.which("emcc") is None:
        raise EnvironmentError("Web release build requires emcc in PATH.")

    _ensure_project_runtime_files(project_root, module_name, debug_mode=False)
    profile_path = _render_release_profile(project_root, platform)

    cmd = [
        sys.executable,
        "-m",
        "SCons",
        f"platform={platform}",
        "target=template_release",
        f"profile={profile_path}",
        f"custom_modules={project_root / 'module'}",
        f"-j{_jobs()}",
    ]
    _run(cmd, godot_dir)

    destination = _build_output_dir(project_root, platform, "release")
    _copy_native_release_outputs(godot_dir, destination, platform)

    if platform == "windows":
        _pack_windows_release(project_root, destination)
    elif platform == "web":
        _pack_web_release(project_root, destination, project_name)

    return destination


def run(project_dir: str, mode: str, platform: str) -> int:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported build mode '{mode}'. Expected one of: {sorted(SUPPORTED_MODES)}")
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(
            f"Unsupported platform '{platform}'. Expected one of: {sorted(SUPPORTED_PLATFORMS)}"
        )

    project_root = Path(project_dir).resolve()
    manifest = load_manifest(project_root)
    module_name = _project_module_name(manifest)
    project_name = str(manifest.get("project", {}).get("name", module_name))
    deps_state = _load_deps_state(project_root)

    if mode == "debug":
        destination = _build_debug(project_root, platform, deps_state, module_name)
    else:
        destination = _build_release(project_root, platform, deps_state, module_name, project_name)

    print(f"Build output: {destination}")
    return 0
