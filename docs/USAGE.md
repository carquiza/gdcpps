# gdcpps Usage

## Status

This document describes the current `gdcpps` workflow. `init`, `deps sync`, `render-profile`, `doctor`, and the Windows/Web `build` paths are implemented in an early but usable form. Linux, macOS, iOS, and Android are still planned.

## Intended Workflow

You can invoke the CLI through the repo-local launchers:

```text
.\gdcpps.bat doctor
./gdcpps.sh doctor
```

Both wrappers call `scripts/gdcpps.py`. The Windows launcher prefers `D:\Source\AIResearch\venv\Scripts\python.exe`, then local `.\.venv` or `.\venv`.

### Create a Project

```text
gdcpps init mygame
```

This should create a consumer project with:

- source directories for C++ gameplay code
- a Godot project content directory
- a project manifest
- build scripts for debug and release

### Sync Dependencies

```text
gdcpps deps sync
gdcpps deps sync path/to/project --godot-source D:\Source\godot --godot-cpp-source D:\Source\AIResearch\gdcpp\godot-cpp
```

This should:

- fetch or update the pinned Godot source revision
- fetch or update the pinned godot-cpp revision
- allow local source overrides for offline or cached development setups
- validate required host tools for the chosen targets

### Check Host Setup

```text
gdcpps doctor
```

Expected behavior:

- report host OS and Python interpreter
- check common tools such as `git`, `scons`, `emcc`, `adb`, and `java`
- report relevant environment variables for Web, Android, and local Godot overrides
- auto-detect Emscripten from `EMSDK` or `D:\Source\emsdk` on Windows hosts

### Build Debug

```text
gdcpps build debug windows --project path/to/project
gdcpps build debug web --project path/to/project
```

Expected behavior:

- build a GDExtension
- place the extension where the generated Godot project can load it
- preserve a fast edit-build-run cycle

### Build Release

```text
gdcpps build release windows --project path/to/project
gdcpps build release web --project path/to/project
```

Expected behavior:

- generate the target-specific Godot feature configuration from the project manifest
- invoke a pinned Godot source build with the generated module glue
- pack project assets into the final artifact where supported

Current status:

- Windows debug is implemented and validated against the `examples/spinning_cube` scaffold
- Windows release is implemented and validated against the embedded-module path
- Web debug is implemented and validated with Emscripten
- Web release is implemented and validated with the `web-small` default profile
- Linux, macOS, iOS, and Android build orchestration are still planned

### Render a Godot Profile

```text
gdcpps render-profile path/to/project windows
gdcpps render-profile path/to/project web
```

Expected behavior:

- load `gdcpps.yaml`
- resolve the selected platform profile plus feature overrides
- write a generated Godot `profile.py` file for use by later build steps

### Run

```text
gdcpps run debug windows
gdcpps run release windows
gdcpps run release web
```

Expected behavior:

- debug launches a Godot binary against `project/` and loads the built GDExtension
- native release launches the built executable or app bundle
- web release serves the build over HTTP for local testing

Current status:

- `run debug windows` is implemented and requires `GODOT_BIN` or a Godot executable on `PATH`
- `run release windows` is implemented and launches the packaged executable from `build/windows/release`
- Web, Linux, macOS, iOS, and Android run helpers are still planned

## Consumer Manifest

A generated project will contain a manifest similar to this:

```yaml
project:
  name: mygame
  godot_version: 4.5.1
  module_name: mygame

profiles:
  base: desktop-default
  web: web-small

features:
  enable: []
  disable:
    - gdscript
    - advanced_gui

platforms:
  windows:
    enable:
      - physics_3d
  web:
    disable:
      - physics_2d
      - physics_3d
      - navigation_2d
      - navigation_3d
```

## Feature Profiles

### `desktop-default`

Intended for Windows, Linux, and macOS.

Expected characteristics:

- balanced feature set
- reasonable desktop functionality
- consumer overrides allowed per platform

### `mobile-default`

Intended for iOS and Android.

Expected characteristics:

- conservative size
- mobile-oriented defaults
- explicit enablement for expensive or niche systems

### `web-small`

Intended for Web builds where initial load size matters.

Expected characteristics:

- size-first settings
- stripped features by default
- explicit opt-in for systems like physics/navigation/threads

## Current Next Steps

Current implementation priorities are:

1. Expand the validated build matrix to Linux and macOS.
2. Add Android and iOS pipelines plus signing/export guidance.
3. Harden diagnostics, examples, and smoke tests.
4. Add CI strategy and onboarding documentation.
