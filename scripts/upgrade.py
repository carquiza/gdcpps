"""Upgrade infrastructure files in an existing gdcpps consumer project."""

from __future__ import annotations

from pathlib import Path

import profile_resolver
from init import (
    _bootstrap_note_text,
    _dirs_file_text,
    _gdcpp_header_text,
    _gdextension_text,
    _game_header_text,
    _game_source_text,
    _launcher_bat_text,
    _launcher_sh_text,
    _load_versions,
    _manifest_text,
    _module_config_text,
    _module_register_header_text,
    _module_register_source_text,
    _module_scsub_text,
    _project_godot_text,
    _main_tscn_text,
    _register_types_header_text,
    _register_types_source_text,
    _root_readme_text,
    _write_text,
)


def run(project_dir: str) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    project_path = Path(project_dir).resolve()

    manifest = profile_resolver.load_manifest(project_path)
    project_section = manifest.get("project", {})
    # Older / hand-edited manifests may omit project.name or project.module_name;
    # fall back gracefully so `upgrade` can still refresh infrastructure files.
    module_name = project_section.get("module_name") or project_section.get("name") or project_path.name
    name = project_section.get("name", module_name)
    class_name = "".join(part.capitalize() for part in module_name.split("_")) + "Main"

    versions = _load_versions(repo_root)
    godot_version = str(versions["godot"]["version"])

    # --- Infrastructure files: always overwrite ---
    infrastructure: list[tuple[Path, str]] = [
        (project_path / "gdcpps.bat", _launcher_bat_text()),
        (project_path / "gdcpps.sh", _launcher_sh_text()),
        (project_path / ".gdcpps" / "README.txt", _bootstrap_note_text()),
        (project_path / "module" / "config.py", _module_config_text()),
        (project_path / "module" / "SCsub", _module_scsub_text(module_name)),
    ]

    for path, content in infrastructure:
        _write_text(path, content)
        print(f"  updated {path.relative_to(project_path)}")

    # --- User-owned files: create only if missing ---
    user_owned: list[tuple[Path, str]] = [
        (project_path / "gdcpps.yaml", _manifest_text(name, godot_version)),
        (project_path / ".gitignore", _dirs_file_text()),
        (project_path / "README.md", _root_readme_text(name)),
        (project_path / "project" / "project.godot", _project_godot_text(name, godot_version)),
        (project_path / "project" / "main.tscn", _main_tscn_text(name, class_name)),
        (project_path / "project" / "bin" / f"{module_name}.gdextension", _gdextension_text(module_name)),
        (project_path / "game" / "include" / "gdcpp.h", _gdcpp_header_text(module_name)),
        (project_path / "game" / "register_types.h", _register_types_header_text(module_name)),
        (project_path / "game" / "register_types.cpp", _register_types_source_text(module_name, class_name)),
        (project_path / "game" / "src" / f"{module_name}_main.h", _game_header_text(module_name, class_name)),
        (project_path / "game" / "src" / f"{module_name}_main.cpp", _game_source_text(module_name, class_name)),
        (project_path / "module" / "register_types.h", _module_register_header_text(module_name)),
        (project_path / "module" / "register_types.cpp", _module_register_source_text(module_name, class_name)),
    ]

    skipped: list[Path] = []
    for path, content in user_owned:
        if path.exists():
            skipped.append(path)
        else:
            _write_text(path, content)
            print(f"  created {path.relative_to(project_path)}")

    # --- Ensure build directories exist ---
    for directory in ("build", "deps", "artifacts"):
        (project_path / directory).mkdir(parents=True, exist_ok=True)

    # --- Summary ---
    if skipped:
        print(f"\n  skipped {len(skipped)} existing file(s):")
        for path in skipped:
            print(f"    {path.relative_to(project_path)}")

    print(f"\nUpgrade complete for {project_path}.")
    return 0
