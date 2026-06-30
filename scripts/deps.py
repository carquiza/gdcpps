"""Dependency sync for gdcpps projects."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


DEFAULT_URLS = {
    "godot": "https://github.com/godotengine/godot.git",
    "godot_cpp": "https://github.com/godotengine/godot-cpp.git",
}

TARGET_DIRS = {
    "godot": "godot",
    "godot_cpp": "godot-cpp",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_versions() -> dict[str, dict[str, str]]:
    with (_repo_root() / "versions.json").open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data


def _run_git(args: list[str], safe_dirs: list[Path] | None = None, cwd: Path | None = None) -> str:
    cmd = ["git"]
    cmd.extend(["-c", "protocol.file.allow=always"])
    for safe_dir in safe_dirs or []:
        cmd.extend(["-c", f"safe.directory={safe_dir.resolve().as_posix()}"])
    cmd.extend(args)

    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        capture_output=True,
    )
    if completed.stdout:
        print(completed.stdout.strip())
    return completed.stdout.strip()


def _try_git(
    args: list[str],
    safe_dirs: list[Path] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = ["git"]
    cmd.extend(["-c", "protocol.file.allow=always"])
    for safe_dir in safe_dirs or []:
        cmd.extend(["-c", f"safe.directory={safe_dir.resolve().as_posix()}"])
    cmd.extend(args)

    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        text=True,
        capture_output=True,
    )


def _resolve_source(source: str | None, default_url: str) -> str:
    if not source:
        return default_url

    candidate = Path(source)
    if candidate.exists():
        return str(candidate.resolve())
    return source


def _checkout_ref(target_dir: Path, ref: str, safe_dirs: list[Path]) -> str:
    # Try origin/<ref> first and check out detached: a plain `checkout <ref>`
    # would reuse a stale local branch from a previous sync instead of the
    # branch tip that was just fetched.
    candidates = [f"origin/{ref}", ref]
    if not ref.endswith("-stable"):
        candidates.extend(
            [
                f"godot-{ref}-stable",
                f"{ref}-stable",
            ]
        )

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)

        completed = _try_git(
            ["-C", str(target_dir), "checkout", "--detach", candidate],
            safe_dirs=safe_dirs,
        )
        if completed.returncode == 0:
            if completed.stdout:
                print(completed.stdout.strip())
            return candidate

    tried = ", ".join(seen)
    raise ValueError(f"Could not resolve git ref '{ref}' in {target_dir}. Tried: {tried}")


def _sync_repo(name: str, spec: dict[str, str], target_root: Path, source_override: str | None) -> dict[str, str]:
    ref = spec["ref"]
    source = _resolve_source(source_override, spec.get("url", DEFAULT_URLS[name]))
    target_dir = target_root / TARGET_DIRS[name]

    local_source = Path(source) if Path(source).exists() else None
    safe_dirs = [target_dir]
    if local_source is not None:
        safe_dirs.append(local_source)

    if target_dir.exists():
        if not (target_dir / ".git").exists():
            raise ValueError(f"Dependency target exists but is not a git checkout: {target_dir}")
        _run_git(["-C", str(target_dir), "remote", "set-url", "origin", source], safe_dirs=safe_dirs)
        _run_git(["-C", str(target_dir), "fetch", "--tags", "origin"], safe_dirs=safe_dirs)
    else:
        target_root.mkdir(parents=True, exist_ok=True)
        _run_git(["clone", source, str(target_dir)], safe_dirs=[local_source] if local_source else None)

    resolved_ref = _checkout_ref(target_dir, ref, safe_dirs)
    revision = _run_git(["-C", str(target_dir), "rev-parse", "HEAD"], safe_dirs=safe_dirs)

    return {
        "path": str(target_dir.resolve()),
        "source": source,
        "ref": resolved_ref,
        "revision": revision,
    }


def _write_state(project_root: Path, state: dict[str, object]) -> None:
    state_path = project_root / ".gdcpps" / "state" / "deps.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8", newline="\n")


def run(
    project_dir: str,
    godot_source: str | None = None,
    godot_cpp_source: str | None = None,
) -> int:
    # Resolution order for each source: explicit --*-source flag, then the
    # GODOT_SOURCE / GODOT_CPP_SOURCE env var (lets you point at a shared local
    # tree once, e.g. ~/Source/godot), then the GitHub URL from versions.json.
    godot_source = godot_source or os.environ.get("GODOT_SOURCE")
    godot_cpp_source = godot_cpp_source or os.environ.get("GODOT_CPP_SOURCE")

    project_root = Path(project_dir).resolve()
    manifest_path = project_root / "gdcpps.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Not a gdcpps project: missing {manifest_path}")

    versions = _load_versions()
    deps_root = project_root / "deps"

    state = {
        "project": str(project_root),
        "dependencies": {
            "godot": _sync_repo("godot", versions["godot"], deps_root, godot_source),
            "godot_cpp": _sync_repo("godot_cpp", versions["godot_cpp"], deps_root, godot_cpp_source),
        },
    }
    _write_state(project_root, state)
    print(f"Wrote {project_root / '.gdcpps' / 'state' / 'deps.json'}")
    return 0
