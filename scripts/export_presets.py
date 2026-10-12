"""Editing project/export_presets.cfg: gdcpps writes the keys it manages and keeps the rest."""

from __future__ import annotations

import re
from pathlib import Path


def cfg_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _parse_cfg(text: str) -> list[tuple[str, list[str]]]:
    """Sections in order as (header, body lines); lines before the first header go under ""."""
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in text.splitlines():
        match = re.match(r"^\[(.+)\]\s*$", line)
        if match:
            sections.append((match.group(1), []))
        else:
            sections[-1][1].append(line)
    return sections


def _set_key(body: list[str], key: str, value: str) -> None:
    prefix = key + "="
    for i, line in enumerate(body):
        if line.startswith(prefix):
            body[i] = prefix + value
            return
    while body and not body[-1].strip():
        body.pop()
    body.append(prefix + value)
    body.append("")


def _default_key(body: list[str], key: str, value: str) -> None:
    if not any(line.startswith(key + "=") for line in body):
        _set_key(body, key, value)


def write_preset(project_dir: Path, name: str, platform: str, export_path: str, options: dict[str, str]) -> None:
    """Creates or updates the preset called `name`. `options` values are cfg literals
    (use cfg_string for strings)."""
    cfg_path = project_dir / "export_presets.cfg"
    sections = _parse_cfg(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else [("", [])]

    index = None
    used = set()
    for header, body in sections:
        match = re.match(r"^preset\.(\d+)$", header)
        if not match:
            continue
        used.add(int(match.group(1)))
        if any(line.strip() == f"name={cfg_string(name)}" for line in body):
            index = int(match.group(1))
    if index is None:
        index = max(used) + 1 if used else 0
        sections.append((f"preset.{index}", []))
        sections.append((f"preset.{index}.options", []))

    def body_of(header: str) -> list[str]:
        for section, body in sections:
            if section == header:
                return body
        sections.append((header, []))
        return sections[-1][1]

    preset = body_of(f"preset.{index}")
    for key, value in (
        ("name", cfg_string(name)),
        ("platform", cfg_string(platform)),
        ("runnable", "true"),
        ("export_filter", cfg_string("all_resources")),
        # The GDExtension is the desktop debug build; on mobile the module is linked into the engine.
        ("exclude_filter", cfg_string("bin/*")),
        ("export_path", cfg_string(export_path)),
    ):
        _set_key(preset, key, value)
    # The editor reads these without defaults (it logs an error for each missing one).
    for key, value in (
        ("dedicated_server", "false"),
        ("custom_features", '""'),
        ("include_filter", '""'),
        ("encryption_include_filters", '""'),
        ("encryption_exclude_filters", '""'),
        ("encrypt_pck", "false"),
        ("encrypt_directory", "false"),
        ("script_export_mode", "2"),
    ):
        _default_key(preset, key, value)

    option_body = body_of(f"preset.{index}.options")
    for key, value in options.items():
        _set_key(option_body, key, value)

    out: list[str] = []
    for header, body in sections:
        if header:
            out.append(f"[{header}]")
        out.extend(body)
        if header and (not body or body[-1].strip()):
            out.append("")
    cfg_path.write_text("\n".join(out).strip("\n") + "\n", encoding="utf-8")
