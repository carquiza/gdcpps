"""Generate a Godot SCons profile from a gdcpps manifest."""

from __future__ import annotations

from pathlib import Path

from profile_resolver import load_manifest, render_profile, resolve_flags


def run(project_dir: str, platform: str, out_path: str | None = None) -> int:
    project_root = Path(project_dir).resolve()
    manifest = load_manifest(project_root)
    flags = resolve_flags(manifest, platform)

    destination = (
        Path(out_path).resolve()
        if out_path
        else project_root / ".gdcpps" / "generated" / f"{platform}.profile.py"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_profile(flags), encoding="utf-8", newline="\n")

    print(f"Generated {destination}")
    return 0
