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
from toolchains import emsdk_env


SUPPORTED_PLATFORMS = {"linux", "windows", "web"}
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


def _web_env() -> dict[str, str]:
    env = emsdk_env()
    if env is None:
        raise EnvironmentError(
            "Web build requires emcc in PATH or a valid EMSDK installation (set the EMSDK environment variable)."
        )
    return env


def _with_git_safe_dirs(env: dict[str, str] | None, *paths: Path) -> dict[str, str]:
    merged = dict(env or os.environ)

    entries: list[str] = []
    count = int(merged.get("GIT_CONFIG_COUNT", "0"))
    for index in range(count):
        key = merged.get(f"GIT_CONFIG_KEY_{index}")
        value = merged.get(f"GIT_CONFIG_VALUE_{index}")
        if key is not None and value is not None:
            entries.extend([key, value])

    for path in paths:
        entries.extend(["safe.directory", path.resolve().as_posix()])

    merged["GIT_CONFIG_COUNT"] = str(len(entries) // 2)
    for index in range(len(entries) // 2):
        merged[f"GIT_CONFIG_KEY_{index}"] = entries[index * 2]
        merged[f"GIT_CONFIG_VALUE_{index}"] = entries[index * 2 + 1]

    return merged


def _gdextension_text(module_name: str) -> str:
    return f"""[configuration]

entry_symbol = "{module_name}_library_init"
compatibility_minimum = "4.5"

[libraries]

windows.debug.x86_32 = "res://bin/lib{module_name}.windows.template_debug.x86_32.dll"
windows.release.x86_32 = "res://bin/lib{module_name}.windows.template_release.x86_32.dll"
windows.debug.x86_64 = "res://bin/lib{module_name}.windows.template_debug.x86_64.dll"
windows.release.x86_64 = "res://bin/lib{module_name}.windows.template_release.x86_64.dll"
windows.debug.arm64 = "res://bin/lib{module_name}.windows.template_debug.arm64.dll"
windows.release.arm64 = "res://bin/lib{module_name}.windows.template_release.arm64.dll"
linux.debug.x86_32 = "res://bin/lib{module_name}.linux.template_debug.x86_32.so"
linux.release.x86_32 = "res://bin/lib{module_name}.linux.template_release.x86_32.so"
linux.debug.x86_64 = "res://bin/lib{module_name}.linux.template_debug.x86_64.so"
linux.release.x86_64 = "res://bin/lib{module_name}.linux.template_release.x86_64.so"
linux.debug.arm32 = "res://bin/lib{module_name}.linux.template_debug.arm32.so"
linux.release.arm32 = "res://bin/lib{module_name}.linux.template_release.arm32.so"
linux.debug.arm64 = "res://bin/lib{module_name}.linux.template_debug.arm64.so"
linux.release.arm64 = "res://bin/lib{module_name}.linux.template_release.arm64.so"
macos.debug = "res://bin/lib{module_name}.macos.template_debug.framework"
macos.release = "res://bin/lib{module_name}.macos.template_release.framework"
web.debug.threads.wasm32 = "res://bin/lib{module_name}.web.template_debug.wasm32.wasm"
web.release.threads.wasm32 = "res://bin/lib{module_name}.web.template_release.wasm32.wasm"
web.debug.wasm32 = "res://bin/lib{module_name}.web.template_debug.wasm32.nothreads.wasm"
web.release.wasm32 = "res://bin/lib{module_name}.web.template_release.wasm32.nothreads.wasm"
"""


def _resolve_manifest_paths(project_root: Path, values: object) -> list[Path]:
    if not isinstance(values, list):
        return []

    resolved: list[Path] = []
    for value in values:
        if not isinstance(value, str) or not value:
            continue
        path = Path(value)
        if not path.is_absolute():
            path = (project_root / path).resolve()
        else:
            path = path.resolve()
        resolved.append(path)
    return resolved


def _python_path_list(paths: list[Path]) -> str:
    if not paths:
        return "[]"
    rendered = ", ".join(f'r\"{path}\"' for path in paths)
    return f"[{rendered}]"


def _string_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _merge_string_lists(*values: object) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in _string_list(value):
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
    return result


def _build_section(manifest: dict, section_name: str) -> dict:
    build = manifest.get("build", {})
    if not isinstance(build, dict):
        return {}
    section = build.get(section_name, {})
    return section if isinstance(section, dict) else {}


def _cpp_standard(manifest: dict) -> str | None:
    build = manifest.get("build", {})
    if not isinstance(build, dict):
        return None
    cpp_standard = build.get("cpp_standard")
    if not isinstance(cpp_standard, str) or not cpp_standard:
        return None
    return cpp_standard


def _build_extensions(project_root: Path, manifest: dict, mode: str) -> dict[str, object]:
    shared = _build_section(manifest, "shared")
    mode_build = _build_section(manifest, mode)

    include_dirs = _merge_string_lists(
        shared.get("include_dirs"),
        shared.get("extra_include_dirs"),
        mode_build.get("include_dirs"),
        mode_build.get("extra_include_dirs"),
    )
    source_globs = _merge_string_lists(
        shared.get("source_globs"),
        shared.get("extra_source_globs"),
        mode_build.get("source_globs"),
        mode_build.get("extra_source_globs"),
    )
    defines = _merge_string_lists(shared.get("defines"), mode_build.get("defines"))
    cxxflags = _merge_string_lists(shared.get("cxxflags"), mode_build.get("cxxflags"))

    return {
        "cpp_standard": _cpp_standard(manifest),
        "include_dirs": _resolve_manifest_paths(project_root, include_dirs),
        "source_globs": _resolve_manifest_paths(project_root, source_globs),
        "defines": defines,
        "cxxflags": cxxflags,
    }


def _python_string_list(values: list[str]) -> str:
    if not values:
        return "[]"
    rendered = ", ".join(repr(value) for value in values)
    return f"[{rendered}]"


def _scons_flag_block(env_name: str, build_extensions: dict[str, object]) -> str:
    cpp_standard = build_extensions["cpp_standard"]
    cxxflags = build_extensions["cxxflags"]
    lines: list[str] = []

    if cpp_standard:
        lines.extend([
            f"if {env_name}[\"platform\"] == \"windows\":",
            f"    {env_name}[\"CXXFLAGS\"] = [flag for flag in {env_name}[\"CXXFLAGS\"] if not str(flag).startswith(\"/std:\")]",
            f"    {env_name}.Append(CXXFLAGS=[\"/std:{cpp_standard}\"])",
            "else:",
            f"    {env_name}[\"CXXFLAGS\"] = [flag for flag in {env_name}[\"CXXFLAGS\"] if not str(flag).startswith(\"-std=\")]",
            f"    {env_name}.Append(CXXFLAGS=[\"-std={cpp_standard}\"])",
        ])

    if cxxflags:
        lines.append(f"{env_name}.Append(CXXFLAGS={_python_string_list(cxxflags)})")

    return "\n".join(lines)


def _indent_block(text: str, prefix: str) -> str:
    if not text:
        return ""
    return "\n".join(prefix + line if line else line for line in text.splitlines())


def _module_scsub_shim_text() -> str:
    return """#!/usr/bin/env python

import importlib.util
import os
from glob import glob

Import("env")
Import("env_modules")

project_root = os.path.abspath(os.path.join(os.path.dirname(str(File("SCsub").srcnode())), ".."))
source_root = os.path.join(project_root, "game")
generated_helper = os.path.join(project_root, ".gdcpps", "generated", "module_build.py")

if os.path.exists(generated_helper):
    spec = importlib.util.spec_from_file_location("gdcpps_module_build", generated_helper)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load generated module helper: {generated_helper}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.configure_module(env, env_modules, project_root)
else:
    env_project = env_modules.Clone()
    env_project.Append(CPPPATH=[
        os.path.join(source_root, "include"),
        os.path.join(source_root, "src"),
    ])

    for cpp_file in sorted(glob(os.path.join(source_root, "src", "*.cpp"))):
        env_project.add_source_files(env.modules_sources, cpp_file)

    env_project.add_source_files(env.modules_sources, os.path.join(source_root, "register_types.cpp"))
    env_project.add_source_files(env.modules_sources, "register_types.cpp")
"""


def _write_module_scsub_shim(project_root: Path) -> None:
    scsub_path = project_root / "module" / "SCsub"
    scsub_path.parent.mkdir(parents=True, exist_ok=True)
    scsub_path.write_text(_module_scsub_shim_text(), encoding="utf-8", newline="\n")


def _write_module_build_script(project_root: Path, module_name: str, manifest: dict) -> Path:
    upper_name = module_name.upper()
    build_extensions = _build_extensions(project_root, manifest, "module")
    flag_block = _scons_flag_block("env_project", build_extensions)
    if flag_block:
        flag_block = _indent_block(flag_block, "    ") + "\n"

    content = f"""#!/usr/bin/env python
import os
from glob import glob

build_include_dirs = {_python_path_list(build_extensions["include_dirs"])}
build_source_globs = {_python_path_list(build_extensions["source_globs"])}
build_defines = {_python_string_list(build_extensions["defines"])}


def configure_module(env, env_modules, project_root):
    env_project = env_modules.Clone()
    env_project["redirect_build_objects"] = False

    source_root = os.path.join(project_root, "game")
    object_root = env.Dir("#bin/obj/external/gdcpps").abspath

    env_project.Append(CPPPATH=[
        os.path.join(source_root, "include"),
        os.path.join(source_root, "src"),
    ] + build_include_dirs)
    env_project.Append(CPPDEFINES=["{upper_name}_MODULE"] + build_defines)
{flag_block}    sources = sorted(glob(os.path.join(source_root, "src", "*.cpp")))
    for pattern in build_source_globs:
        sources.extend(sorted(glob(pattern, recursive=True)))

    seen = set()
    ordered_sources = []
    for source in sources:
        if source in seen:
            continue
        seen.add(source)
        ordered_sources.append(source)

    def object_target_for(source):
        source = os.path.abspath(source)
        try:
            relative_to_project = os.path.relpath(source, project_root)
            if not relative_to_project.startswith(".."):
                relative_object = os.path.splitext(relative_to_project)[0]
            else:
                raise ValueError
        except ValueError:
            drive, tail = os.path.splitdrive(source)
            relative_object = os.path.splitext(tail.lstrip("\\\\/"))[0]
            if drive:
                relative_object = os.path.join(drive.rstrip(":\\\\"), relative_object)
        return os.path.join(object_root, relative_object)

    for source in ordered_sources:
        built_objects = env_project.Object(target=object_target_for(source), source=source)
        env.modules_sources.extend(env_project.Flatten([built_objects]))

    for source in (
        os.path.join(source_root, "register_types.cpp"),
        os.path.join(project_root, "module", "register_types.cpp"),
    ):
        built_objects = env_project.Object(target=object_target_for(source), source=source)
        env.modules_sources.extend(env_project.Flatten([built_objects]))
"""
    helper_path = project_root / ".gdcpps" / "generated" / "module_build.py"
    helper_path.parent.mkdir(parents=True, exist_ok=True)
    helper_path.write_text(content, encoding="utf-8", newline="\n")
    return helper_path


def _ensure_project_runtime_files(project_root: Path, module_name: str, debug_mode: bool) -> None:
    godot_dir = project_root / "project" / ".godot"
    godot_dir.mkdir(parents=True, exist_ok=True)
    project_bin = project_root / "project" / "bin"
    project_bin.mkdir(parents=True, exist_ok=True)

    cache_path = godot_dir / "global_script_class_cache.cfg"
    if not cache_path.exists():
        cache_path.write_text('[""]\n\nlist=[]\n', encoding="utf-8", newline="\n")

    gdextension_path = project_bin / f"{module_name}.gdextension"
    gdextension_path.write_text(_gdextension_text(module_name), encoding="utf-8", newline="\n")

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
    manifest = load_manifest(project_root)
    build_extensions = _build_extensions(project_root, manifest, "debug")
    flag_block = _scons_flag_block("env", build_extensions)
    if flag_block:
        flag_block = flag_block + "\n"
    content = f"""#!/usr/bin/env python
import os
from glob import glob

project_root = r"{project_root.resolve()}"
godot_cpp_dir = r"{godot_cpp_dir.resolve()}"
game_dir = os.path.join(project_root, "game")
project_dir = os.path.join(project_root, "project")
build_include_dirs = {_python_path_list(build_extensions["include_dirs"])}
build_source_globs = {_python_path_list(build_extensions["source_globs"])}
build_defines = {_python_string_list(build_extensions["defines"])}

env = SConscript(os.path.join(godot_cpp_dir, "SConstruct"))
env.Append(CPPPATH=[os.path.join(game_dir, "include"), game_dir] + build_include_dirs)
env.Append(CPPDEFINES=["{upper_name}_GDEXTENSION"] + build_defines)
{flag_block}

sources = sorted(glob(os.path.join(game_dir, "src", "*.cpp")))
for pattern in build_source_globs:
    sources.extend(sorted(glob(pattern, recursive=True)))
sources = list(dict.fromkeys(sources))
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
    if destination.exists():
        try:
            shutil.rmtree(destination)
        except PermissionError as exc:
            raise PermissionError(
                f"Cannot replace build output at {destination}. Close any running app or process using files in that directory and retry."
            ) from exc
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

    manifest = load_manifest(project_root)
    env = None
    if platform == "web":
        env = _web_env()
    env = _with_git_safe_dirs(env, godot_cpp_dir)

    _ensure_project_runtime_files(project_root, module_name, debug_mode=True)
    _write_module_scsub_shim(project_root)
    _write_module_build_script(project_root, module_name, manifest)
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
    _run(cmd, project_root, env=env)

    project_bin = project_root / "project" / "bin"
    artifacts = list(project_bin.glob(f"lib{module_name}.{platform}*"))
    if not artifacts:
        raise FileNotFoundError(f"No debug artifacts found in {project_bin}")

    destination = _build_output_dir(project_root, platform, "debug")
    _copy_files(artifacts, destination)
    return destination


def _copy_native_release_outputs(godot_dir: Path, destination: Path, platform: str) -> list[Path]:
    bin_dir = godot_dir / "bin"
    if platform == "windows":
        sources = list(bin_dir.glob("godot.windows.template_release*.exe"))
    elif platform == "linux":
        sources = list(bin_dir.glob("godot.linuxbsd.template_release*")) + list(
            bin_dir.glob("godot.linux.template_release*")
        )
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


def _pack_linux_release(project_root: Path, build_dir: Path) -> None:
    project_dir = project_root / "project"
    executables = [path for path in sorted(build_dir.glob("godot.linux*.template_release*")) if path.is_file()]
    if not executables:
        raise FileNotFoundError(f"No Linux release executable found in {build_dir}")

    for exe_path in executables:
        pck_path = Path(str(exe_path) + ".pck")
        pack.write_pck(str(project_dir), str(pck_path))


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

    manifest = load_manifest(project_root)
    env = None
    if platform == "web":
        env = _web_env()
    godot_cpp_dir = Path(deps_state["dependencies"]["godot_cpp"]["path"])
    env = _with_git_safe_dirs(env, godot_dir, godot_cpp_dir)

    _ensure_project_runtime_files(project_root, module_name, debug_mode=False)
    _write_module_scsub_shim(project_root)
    _write_module_build_script(project_root, module_name, manifest)
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
    _run(cmd, godot_dir, env=env)

    destination = _build_output_dir(project_root, platform, "release")
    _copy_native_release_outputs(godot_dir, destination, platform)

    if platform == "windows":
        _pack_windows_release(project_root, destination)
    elif platform == "linux":
        _pack_linux_release(project_root, destination)
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
