"""Toolchain discovery helpers for gdcpps."""

from __future__ import annotations

import os
from pathlib import Path


def find_emsdk_root() -> Path | None:
    candidates: list[Path] = []

    env_root = os.environ.get("EMSDK")
    if env_root:
        candidates.append(Path(env_root))

    candidates.append(Path(r"D:\Source\emsdk"))

    for candidate in candidates:
        emcc = candidate / "upstream" / "emscripten" / "emcc.bat"
        if emcc.exists():
            return candidate.resolve()
    return None


def emsdk_env() -> dict[str, str] | None:
    root = find_emsdk_root()
    if root is None:
        return None

    node_dirs = sorted((root / "node").glob("*"))
    python_dirs = sorted((root / "python").glob("*"))
    node_bin = node_dirs[0] / "bin" if node_dirs else None
    python_bin = python_dirs[0] if python_dirs else None

    path_entries = [
        str(root / "upstream" / "emscripten"),
        str(root / "upstream" / "bin"),
    ]
    if node_bin and node_bin.exists():
        path_entries.append(str(node_bin))
    if python_bin and python_bin.exists():
        path_entries.append(str(python_bin))

    env = dict(os.environ)
    env["EMSDK"] = str(root)
    env["EM_CONFIG"] = str(root / ".emscripten")
    env["PATH"] = os.pathsep.join(path_entries + [env.get("PATH", "")])
    return env
