"""Environment diagnostics for gdcpps."""

from __future__ import annotations

import os
import platform
import shutil
import sys
from importlib.util import find_spec

from toolchains import find_emsdk_root


TOOL_CHECKS = [
    ("git", "git", "required for dependency sync"),
    ("adb", "adb", "useful for Android device deployment"),
    ("java", "java", "required by Android tooling"),
]

ENV_CHECKS = [
    ("GDCPPS_HOME", "required by generated project launcher scripts"),
    ("ANDROID_SDK_ROOT", "required for Android builds"),
    ("ANDROID_HOME", "legacy Android SDK variable; accepted if SDK root is unset"),
    ("ANDROID_NDK_ROOT", "required for Android native builds"),
    ("EMSDK", "useful for locating Emscripten installation"),
    ("GODOT_SOURCE", "deps sync: clone Godot from this local tree instead of GitHub"),
    ("GODOT_CPP_SOURCE", "deps sync: clone godot-cpp from this local tree instead of GitHub"),
    ("GODOT_BIN", "optional override for local Godot editor/runtime"),
]


def _tool_status(label: str, exe_name: str, note: str) -> str:
    path = shutil.which(exe_name)
    if path:
        return f"[ok]   tool:{label:<12} {path}"
    return f"[miss] tool:{label:<12} not found ({note})"


def _emscripten_status() -> str:
    path = shutil.which("emcc")
    if path:
        return f"[ok]   tool:emscripten   {path}"

    emsdk_root = find_emsdk_root()
    if emsdk_root is not None:
        return f"[ok]   tool:emscripten   {emsdk_root / 'upstream' / 'emscripten' / 'emcc.bat'}"

    return "[miss] tool:emscripten   not found (required for Web builds)"


def _scons_status() -> str:
    if find_spec("SCons") is not None:
        return f"[ok]   tool:scons-module {sys.executable} -m SCons"

    path = shutil.which("scons")
    if path:
        return f"[ok]   tool:scons        {path}"

    return "[miss] tool:scons        not found (required for Godot and GDExtension builds)"


def _pyyaml_status() -> str:
    if find_spec("yaml") is not None:
        return "[ok]   pkg:pyyaml        installed"
    return "[miss] pkg:pyyaml        not found (required to load gdcpps.yaml manifests)"


def _env_status(name: str, note: str) -> str:
    value = os.environ.get(name)
    if value:
        return f"[ok]   env:{name:<15} {value}"
    return f"[miss] env:{name:<15} unset ({note})"


def _host_notes() -> list[str]:
    system = platform.system().lower()
    notes = [f"Host OS: {platform.system()} {platform.release()}"]
    notes.append(f"Python: {sys.executable}")

    if system == "windows":
        notes.append("iOS and macOS release builds require an Apple host/toolchain.")
    elif system == "darwin":
        notes.append("Apple host detected; macOS/iOS targets can be validated here.")
        if shutil.which("clang") is None:
            notes.append("clang not found; install the Xcode command line tools (xcode-select --install) for macOS builds.")
    else:
        notes.append("Desktop and Web builds are expected to be primary on this host.")

    return notes


def run() -> int:
    for line in _host_notes():
        print(line)

    print("")
    print("Tools")
    print(_scons_status())
    print(_pyyaml_status())
    print(_emscripten_status())
    for label, exe_name, note in TOOL_CHECKS:
        print(_tool_status(label, exe_name, note))

    print("")
    print("Environment")
    for name, note in ENV_CHECKS:
        print(_env_status(name, note))

    return 0
