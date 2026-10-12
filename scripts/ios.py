"""iOS release: engine library with the module linked in, Xcode template, export, signed app.

`gdcpps build release ios` builds the engine as a static library for arm64 with the project's
module, wraps it in Godot's Xcode template (`godot_ios.zip`), exports the project with the Godot
editor against that template (an "iOS" preset in `project/export_presets.cfg`, written from the
manifest), and builds a signed `.app` with xcodebuild. `gdcpps run release ios` installs that app
on a connected device and launches it.

Manifest:

    platforms:
      ios:
        export:
          bundle_id: com.example.mygame   # required
          team_id: ABCDE12345             # required: the Apple developer team that signs
          display_name: My Game           # optional, defaults to project.name
          icon: path/to/icon.png          # 1024x1024; required unless project.godot sets an icon
          min_ios_version: "15.0"         # optional; the oldest Xcode 26+ accepts
          device: <udid or name>          # optional, for `run`: defaults to the first connected
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


PRESET_NAME = "iOS"


def engine_build_args() -> list[str]:
    # Metal is Godot's default rendering driver on iOS; Vulkan would need an iOS MoltenVK
    # (Homebrew's is macOS only), so the template is built without it.
    return ["arch=arm64", "metal=yes", "vulkan=no"]


def export_config(manifest: dict) -> dict:
    platforms = manifest.get("platforms") or {}
    ios_cfg = platforms.get("ios") if isinstance(platforms, dict) else None
    export = (ios_cfg or {}).get("export") if isinstance(ios_cfg, dict) else None
    export = dict(export) if isinstance(export, dict) else {}
    missing = [key for key in ("bundle_id", "team_id") if not export.get(key)]
    if missing:
        raise ValueError(
            "iOS export needs platforms.ios.export." + " and platforms.ios.export.".join(missing) + " in gdcpps.yaml"
        )
    project = manifest.get("project") or {}
    export.setdefault("display_name", str(project.get("name") or project.get("module_name") or "game"))
    # Godot 4.5 defaults to 14.0; Xcode 26+ builds for 15.0 and later only.
    export.setdefault("min_ios_version", "15.0")
    return export


def binary_name(manifest: dict) -> str:
    project = manifest.get("project") or {}
    name = str(project.get("name") or project.get("module_name") or "game")
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def _resolve_godot_editor() -> str:
    env_bin = os.environ.get("GODOT_BIN")
    if env_bin:
        return env_bin
    for candidate in ("godot", "godot4"):
        path = shutil.which(candidate)
        if path:
            return path
    app = Path("/Applications/Godot.app/Contents/MacOS/Godot")
    if app.exists():
        return str(app)
    raise FileNotFoundError("The iOS export needs the Godot editor: set GODOT_BIN or install /Applications/Godot.app.")


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


# --- template ---------------------------------------------------------------------------------


def _strip_moltenvk(pbxproj: Path) -> None:
    # The stock template links MoltenVK.xcframework; a Metal-only build has none to link.
    lines = pbxproj.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [line for line in lines if "MoltenVK.xcframework" not in line]
    pbxproj.write_text("".join(kept), encoding="utf-8")


def build_template(godot_dir: Path, library: Path, destination: Path) -> Path:
    """Godot's Xcode template with the release library in place, zipped as an export template."""
    with tempfile.TemporaryDirectory() as temp:
        app_dir = Path(temp) / "ios_xcode"
        shutil.copytree(godot_dir / "misc" / "dist" / "ios_xcode", app_dir)
        shutil.copy2(library, app_dir / "libgodot.ios.release.xcframework" / "ios-arm64" / "libgodot.a")
        _strip_moltenvk(app_dir / "godot_ios.xcodeproj" / "project.pbxproj")
        archive = shutil.make_archive(str(destination / "godot_ios"), "zip", root_dir=app_dir)
    return Path(archive)


# --- export preset ----------------------------------------------------------------------------


def _cfg_string(value: str) -> str:
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


def _default_key(body: list[str], key: str, value: str) -> None:
    if not any(line.startswith(key + "=") for line in body):
        _set_key(body, key, value)


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


def write_export_preset(project_dir: Path, template: Path, export: dict, export_path: str, icon: Path | None) -> None:
    """Creates or updates the "iOS" preset; keys gdcpps doesn't manage are left as they are."""
    cfg_path = project_dir / "export_presets.cfg"
    sections = _parse_cfg(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else [("", [])]

    index = None
    used = set()
    for header, body in sections:
        match = re.match(r"^preset\.(\d+)$", header)
        if not match:
            continue
        used.add(int(match.group(1)))
        if any(line.strip() == f"name={_cfg_string(PRESET_NAME)}" for line in body):
            index = int(match.group(1))
    if index is None:
        index = max(used) + 1 if used else 0
        sections.append((f"preset.{index}", []))
        sections.append((f"preset.{index}.options", []))

    def body_of(header: str) -> list[str]:
        for name, body in sections:
            if name == header:
                return body
        sections.append((header, []))
        return sections[-1][1]

    preset = body_of(f"preset.{index}")
    for key, value in (
        ("name", _cfg_string(PRESET_NAME)),
        ("platform", _cfg_string("iOS")),
        ("runnable", "true"),
        ("export_filter", _cfg_string("all_resources")),
        # The GDExtension is the desktop debug build; on iOS the module is linked into the engine.
        ("exclude_filter", _cfg_string("bin/*")),
        ("export_path", _cfg_string(export_path)),
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

    options = body_of(f"preset.{index}.options")
    for key, value in (
        ("custom_template/release", _cfg_string(str(template))),
        ("application/app_store_team_id", _cfg_string(str(export["team_id"]))),
        ("application/bundle_identifier", _cfg_string(str(export["bundle_id"]))),
        ("application/export_project_only", "true"),
        ("application/min_ios_version", _cfg_string(str(export["min_ios_version"]))),
    ):
        _set_key(options, key, value)
    if icon is not None:
        _set_key(options, "icons/icon_1024x1024", _cfg_string(str(icon)))

    out: list[str] = []
    for header, body in sections:
        if header:
            out.append(f"[{header}]")
        out.extend(body)
        if header and (not body or body[-1].strip()):
            out.append("")
    cfg_path.write_text("\n".join(out).strip("\n") + "\n", encoding="utf-8")


# --- export and app ---------------------------------------------------------------------------


def _set_display_name(xcode_dir: Path, name: str, display_name: str) -> None:
    plist_path = xcode_dir / name / f"{name}-Info.plist"
    if not plist_path.exists():
        return
    with open(plist_path, "rb") as handle:
        info = plistlib.load(handle)
    info["CFBundleDisplayName"] = display_name
    with open(plist_path, "wb") as handle:
        plistlib.dump(info, handle)


def package_release(project_root: Path, manifest: dict, godot_dir: Path, destination: Path) -> None:
    from build import ensure_project_runtime_files, project_module_name

    export = export_config(manifest)
    name = binary_name(manifest)
    libraries = sorted(destination.glob("libgodot.ios.template_release*.a"))
    if not libraries:
        raise FileNotFoundError(f"No iOS engine library in {destination}")
    template = build_template(godot_dir, libraries[0], destination)

    xcode_dir = destination / "xcode"
    if xcode_dir.exists():
        shutil.rmtree(xcode_dir)
    xcode_dir.mkdir(parents=True)
    project_dir = project_root / "project"
    export_target = xcode_dir / f"{name}.ipa"  # with export_project_only, the Xcode project lands beside it
    icon = (project_root / str(export["icon"])).resolve() if export.get("icon") else None
    if icon is not None and not icon.exists():
        raise FileNotFoundError(f"platforms.ios.export.icon not found: {icon}")
    write_export_preset(project_dir, template, export, os.path.relpath(export_target, project_dir), icon)

    # The editor needs the game's classes to export its scenes: load the desktop debug
    # GDExtension while exporting (the preset leaves it out of the package).
    module_name = project_module_name(manifest)
    has_debug_extension = any((project_dir / "bin").glob(f"lib{module_name}.macos.template_debug*"))
    if has_debug_extension:
        ensure_project_runtime_files(project_root, module_name, debug_mode=True)
    else:
        print("warning: no macOS debug build of the extension; scenes using its classes may not export. Run `gdcpps build debug macos` first.")

    _run([_resolve_godot_editor(), "--headless", "--path", str(project_dir), "--export-release", PRESET_NAME, str(export_target)])
    xcodeproj = xcode_dir / f"{name}.xcodeproj"
    if not xcodeproj.exists():
        raise FileNotFoundError(f"The Godot export wrote no Xcode project at {xcodeproj}")
    _set_display_name(xcode_dir, name, str(export["display_name"]))

    derived = destination / "DerivedData"
    _run(
        [
            "xcodebuild",
            "-project", str(xcodeproj),
            "-scheme", name,
            "-configuration", "Release",
            "-destination", "generic/platform=iOS",
            "-derivedDataPath", str(derived),
            "-allowProvisioningUpdates",
            f"DEVELOPMENT_TEAM={export['team_id']}",
            "CODE_SIGN_STYLE=Automatic",
            # Godot's template signs Release for distribution; this is a build for your devices.
            "CODE_SIGN_IDENTITY=Apple Development",
            "build",
        ]
    )
    apps = sorted((derived / "Build" / "Products" / "Release-iphoneos").glob("*.app"))
    if not apps:
        raise FileNotFoundError(f"xcodebuild produced no .app under {derived}")
    app = destination / apps[0].name
    if app.exists():
        shutil.rmtree(app)
    shutil.copytree(apps[0], app, symlinks=True)
    print(f"iOS app: {app}")


# --- run on a device --------------------------------------------------------------------------


def _devices() -> list[dict]:
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp) / "devices.json"
        subprocess.run(
            ["xcrun", "devicectl", "list", "devices", "--json-output", str(out)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        data = json.loads(out.read_text(encoding="utf-8"))
    return data.get("result", {}).get("devices", [])


def _pick_device(wanted: str | None) -> str:
    candidates = []
    for device in _devices():
        hardware = device.get("hardwareProperties", {})
        props = device.get("deviceProperties", {})
        connection = device.get("connectionProperties", {})
        if hardware.get("platform") != "iOS" or hardware.get("reality") != "physical":
            continue
        ident = device.get("identifier", "")
        udid = hardware.get("udid", "")
        label = props.get("name", "")
        if wanted and wanted not in (ident, udid, label):
            continue
        if connection.get("pairingState") != "paired":
            continue
        candidates.append((ident, label))
    if not candidates:
        raise RuntimeError("No paired iOS device found" + (f" matching '{wanted}'" if wanted else "") + " (xcrun devicectl list devices).")
    print(f"Device: {candidates[0][1]} ({candidates[0][0]})")
    return candidates[0][0]


def run_release(project_root: Path, manifest: dict, game_args: list[str]) -> int:
    export = export_config(manifest)
    build_dir = project_root / "build" / "ios" / "release"
    apps = sorted(build_dir.glob("*.app"))
    if not apps:
        raise FileNotFoundError(f"No iOS app in {build_dir}. Run `gdcpps build release ios` first.")
    device = _pick_device(os.environ.get("GDCPPS_IOS_DEVICE") or export.get("device"))
    _run(["xcrun", "devicectl", "device", "install", "app", "--device", device, str(apps[0])])
    _run(
        ["xcrun", "devicectl", "device", "process", "launch", "--terminate-existing", "--device", device, str(export["bundle_id"])]
        + game_args
    )
    return 0
