"""Android release: engine library with the module linked in, template APK, export, signed APK.

`gdcpps build release android` builds the engine for arm64 with the project's module
(`libgodot_android.so`), turns it into Godot's release template APK with gradle, exports the
project with the Godot editor against that template (an "Android" preset in
`project/export_presets.cfg`, written from the manifest) and signs the APK. `gdcpps run release
android` installs it on a connected device (adb) and launches it.

Manifest:

    platforms:
      android:
        export:
          package: com.example.mygame     # required
          display_name: My Game           # optional, defaults to project.name
          icon: path/to/icon.png          # optional launcher icon (192x192 or larger)
          keystore: path/to/release.jks   # optional; default: Godot's debug keystore
          keystore_user: alias            # with keystore
          keystore_password_env: VAR      # with keystore: the environment variable holding the password
          device: <adb serial>            # optional, for `run`: defaults to the only device
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from export_presets import cfg_string, write_preset


PRESET_NAME = "Android"


def engine_build_args() -> list[str]:
    return ["arch=arm64"]


def export_config(manifest: dict) -> dict:
    platforms = manifest.get("platforms") or {}
    android_cfg = platforms.get("android") if isinstance(platforms, dict) else None
    export = (android_cfg or {}).get("export") if isinstance(android_cfg, dict) else None
    export = dict(export) if isinstance(export, dict) else {}
    if not export.get("package"):
        raise ValueError("Android export needs platforms.android.export.package in gdcpps.yaml")
    project = manifest.get("project") or {}
    export.setdefault("display_name", str(project.get("name") or project.get("module_name") or "game"))
    return export


def binary_name(manifest: dict) -> str:
    project = manifest.get("project") or {}
    return re.sub(r"[^A-Za-z0-9_]", "_", str(project.get("name") or project.get("module_name") or "game"))


def _run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=True)


def _godot_editor() -> str:
    from ios import _resolve_godot_editor

    return _resolve_godot_editor()


def _debug_keystore_path() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", "")) / "Godot" / "keystores" / "debug.keystore"
    mac = Path.home() / "Library" / "Application Support" / "Godot"
    if mac.exists():
        return mac / "keystores" / "debug.keystore"
    return Path.home() / ".local" / "share" / "godot" / "keystores" / "debug.keystore"


def _signing(project_root: Path, export: dict) -> tuple[Path, str, str]:
    """(keystore, alias, password) for the release APK."""
    if export.get("keystore"):
        keystore = (project_root / str(export["keystore"])).resolve()
        env_name = str(export.get("keystore_password_env") or "")
        password = os.environ.get(env_name, "") if env_name else ""
        if not keystore.exists() or not export.get("keystore_user") or not password:
            raise ValueError(
                "platforms.android.export.keystore needs the file, keystore_user, and a password in the "
                "variable named by keystore_password_env"
            )
        return keystore, str(export["keystore_user"]), password
    # Development builds: Godot's own debug keystore (made here if the editor hasn't yet).
    keystore = _debug_keystore_path()
    if not keystore.exists():
        keystore.parent.mkdir(parents=True, exist_ok=True)
        _run(
            [
                "keytool", "-genkeypair", "-v", "-keystore", str(keystore), "-storepass", "android",
                "-alias", "androiddebugkey", "-keypass", "android", "-keyalg", "RSA", "-keysize", "2048",
                "-validity", "10000", "-dname", "CN=Android Debug,O=Android,C=US",
            ]
        )
    return keystore, "androiddebugkey", "android"


def build_template(godot_dir: Path, destination: Path) -> Path:
    """Godot's release template APK around the freshly built engine library (gradle)."""
    java_dir = godot_dir / "platform" / "android" / "java"
    gradlew = java_dir / ("gradlew.bat" if os.name == "nt" else "gradlew")
    _run([str(gradlew), "generateGodotTemplates"], cwd=java_dir)
    apk = godot_dir / "bin" / "android_release.apk"
    if not apk.exists():
        raise FileNotFoundError(f"gradle produced no {apk}")
    target = destination / apk.name
    shutil.copy2(apk, target)
    return target


def package_release(project_root: Path, manifest: dict, godot_dir: Path, destination: Path) -> None:
    from build import ensure_project_runtime_files, project_module_name

    export = export_config(manifest)
    name = binary_name(manifest)
    template = build_template(godot_dir, destination)
    keystore, alias, password = _signing(project_root, export)

    project_dir = project_root / "project"
    apk = destination / f"{name}.apk"
    options = {
        "custom_template/release": cfg_string(str(template)),
        "gradle_build/use_gradle_build": "false",
        "package/unique_name": cfg_string(str(export["package"])),
        "package/name": cfg_string(str(export["display_name"])),
        "package/signed": "true",
        "architectures/arm64-v8a": "true",
        "architectures/armeabi-v7a": "false",
        "architectures/x86": "false",
        "architectures/x86_64": "false",
    }
    if export.get("icon"):
        icon = (project_root / str(export["icon"])).resolve()
        if not icon.exists():
            raise FileNotFoundError(f"platforms.android.export.icon not found: {icon}")
        options["launcher_icons/main_192x192"] = cfg_string(str(icon))
    write_preset(project_dir, PRESET_NAME, "Android", os.path.relpath(apk, project_dir), options)

    # The editor needs the game's classes to export its scenes (see ios.py).
    module_name = project_module_name(manifest)
    if any((project_dir / "bin").glob(f"lib{module_name}.*.template_debug*")):
        ensure_project_runtime_files(project_root, module_name, debug_mode=True)

    # The keystore goes in through the environment, so its password never lands in the preset.
    env = dict(os.environ)
    env["GODOT_ANDROID_KEYSTORE_RELEASE_PATH"] = str(keystore)
    env["GODOT_ANDROID_KEYSTORE_RELEASE_USER"] = alias
    env["GODOT_ANDROID_KEYSTORE_RELEASE_PASSWORD"] = password
    _run([_godot_editor(), "--headless", "--path", str(project_dir), "--export-release", PRESET_NAME, str(apk)], env=env)
    if not apk.exists():
        raise FileNotFoundError(f"The Godot export wrote no {apk}")
    print(f"Android APK: {apk}")


# --- run on a device --------------------------------------------------------------------------


def _adb() -> str:
    home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if home:
        candidate = Path(home) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
        if candidate.exists():
            return str(candidate)
    found = shutil.which("adb")
    if not found:
        raise FileNotFoundError("adb not found: set ANDROID_HOME or put platform-tools on PATH")
    return found


def _pick_device(adb: str, wanted: str | None) -> str:
    out = subprocess.run([adb, "devices"], check=True, capture_output=True, text=True).stdout
    serials = [line.split()[0] for line in out.splitlines()[1:] if line.strip().endswith("device")]
    if wanted:
        if wanted not in serials:
            raise RuntimeError(f"Android device {wanted} is not connected (adb devices: {serials})")
        return wanted
    if not serials:
        raise RuntimeError("No Android device connected (adb devices). Enable USB debugging and connect one.")
    if len(serials) > 1:
        raise RuntimeError(f"Several Android devices connected {serials}: set platforms.android.export.device or GDCPPS_ANDROID_DEVICE")
    return serials[0]


def run_release(project_root: Path, manifest: dict, game_args: list[str]) -> int:
    export = export_config(manifest)
    apk = project_root / "build" / "android" / "release" / f"{binary_name(manifest)}.apk"
    if not apk.exists():
        raise FileNotFoundError(f"No APK at {apk}. Run `gdcpps build release android` first.")
    adb = _adb()
    device = _pick_device(adb, os.environ.get("GDCPPS_ANDROID_DEVICE") or export.get("device"))
    _run([adb, "-s", device, "install", "-r", str(apk)])
    package = str(export["package"])
    cmd = [adb, "-s", device, "shell", "am", "start", "-S", "-n", f"{package}/com.godot.game.GodotApp"]
    if game_args:
        # GodotActivity reads its command line from this string-array extra.
        cmd += ["--esa", "command_line_params", ",".join(arg.replace(",", "\\,") for arg in game_args)]
    _run(cmd)
    return 0
