# gdcpps Usage

## Status

This document describes the current `gdcpps` workflow. `init`, `deps sync`, `render-profile`, `doctor`, and the Windows/Linux/macOS/Web `build` paths are implemented in an early but usable form. iOS and Android are still planned.

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
gdcpps deps sync path/to/project --godot-source ~/Source/godot --godot-cpp-source ~/Source/godot-cpp
```

Without a project path, `deps sync` uses the current directory.

This should:

- fetch or update the pinned Godot source revision
- fetch or update the pinned godot-cpp revision
- allow local source overrides for offline or cached development setups
- validate required host tools for the chosen targets

#### Source resolution and a shared local tree

For each dependency, `deps sync` resolves the clone source in this order:

1. the explicit `--godot-source` / `--godot-cpp-source` flag
2. the `GODOT_SOURCE` / `GODOT_CPP_SOURCE` environment variable
3. the GitHub URL pinned in `versions.json`

A local path is cloned into the project's `deps/` (on the same filesystem git
hardlinks the object store, so the copy is fast and cheap). The version that is
actually checked out is always the ref pinned in `versions.json` — the local
tree just needs to contain it.

Recommended setup for anyone who rebuilds the engine often: keep one canonical
checkout of each upstream and point gdcpps at it via the env vars, then `deps
sync` is local, fast, and offline. Each project still gets its own working copy
under `deps/`, which keeps per-project build state (objects, `bin/`) isolated.

```text
export GODOT_SOURCE=~/Source/godot
export GODOT_CPP_SOURCE=~/Source/godot-cpp

# stay updated: fetch upstream, bump the ref in versions.json, then re-sync
git -C ~/Source/godot fetch --tags
gdcpps deps sync path/to/project
```

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
gdcpps build debug linux --project path/to/project
gdcpps build debug web --project path/to/project
```

Expected behavior:

- build a GDExtension
- place the extension where the generated Godot project can load it
- preserve a fast edit-build-run cycle

### Build Release

```text
gdcpps build release windows --project path/to/project
gdcpps build release linux --project path/to/project
gdcpps build release macos --project path/to/project
gdcpps build release web --project path/to/project
```

> macOS release builds compile the Godot engine, which links MoltenVK for Vulkan.
> Install it with `brew install molten-vk` (Godot finds the xcframework under
> `/opt/homebrew/Frameworks`). Debug/GDExtension builds do not need it.

Expected behavior:

- generate the target-specific Godot feature configuration from the project manifest
- invoke a pinned Godot source build with the generated module glue
- pack project assets into the final artifact where supported

Current status:

- Windows debug is implemented and validated against the `examples/spinning_cube` scaffold
- Windows release is implemented and validated against the embedded-module path
- Web debug is implemented and validated with Emscripten
- Web release is implemented and validated with the `web-small` default profile
- Linux debug and release are implemented; broader validation is still in progress
- macOS debug and release are implemented; release ships the engine binary with a sidecar `.pck` (a signed `.app` bundle is a planned publish step)
- iOS and Android build orchestration are still planned

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
gdcpps run debug windows -- --my-game-flag value
```

Arguments after `--` are forwarded to the launched game process (in debug mode, appended after `--path <project>`; in release mode, passed to the packaged executable). Note that `--project` must come before the mode/platform positionals when forwarding extra arguments.

Expected behavior:

- debug launches a Godot binary against `project/` and loads the built GDExtension
- native release launches the built executable or app bundle
- web release serves the build over HTTP for local testing

Current status:

- `run debug` is implemented for windows, linux, and macos and requires `GODOT_BIN` or a Godot executable on `PATH`
- `run release` is implemented for windows, linux, and macos and launches the packaged executable from `build/<platform>/release`
- Web, iOS, and Android run helpers are still planned

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

## Build Hooks

`gdcpps` now supports a first manifest-driven hook surface for bringing in shared native code without editing generated files.

Implemented fields:

```yaml
build:
  cpp_standard: c++20
  shared:
    extra_include_dirs: []
    extra_source_globs: []
    defines: []
    cxxflags: []
  debug:
    extra_include_dirs: []
    extra_source_globs: []
    defines: []
    cxxflags: []
  module:
    extra_include_dirs: []
    extra_source_globs: []
    defines: []
    cxxflags: []

platforms:
  windows:
    build:
      shared:
        extra_include_dirs: []
        extra_source_globs: []
        defines: []
        cxxflags: []
      debug:
        extra_include_dirs: []
        extra_source_globs: []
        defines: []
        cxxflags: []
      module:
        extra_include_dirs: []
        extra_source_globs: []
        defines: []
        cxxflags: []
```

These fields are applied to the generated debug GDExtension build glue and the generated module build glue.
Platform-specific build sections are merged after the top-level `build.shared` and `build.<mode>` sections for the active target platform.
`include_dirs` and `source_globs` are accepted as aliases for `extra_include_dirs` and `extra_source_globs`.

For release/module builds, `gdcpps` now assigns explicit object targets for hooked external sources so temporary `.obj` files stay under the Godot build tree instead of being emitted next to the original source files.

The broader extension model is documented in `docs/HOOKS.md`.

Typical use cases:

- monorepo projects with shared native code outside `game/src`
- shared simulation or engine code compiled into both debug and release builds
- project-specific include roots and C++ standard settings

Future expansions such as library dirs, link flags, and optional Python hook files are still planned.

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

1. Validate macOS artifacts on an Apple host and expand the build matrix to mobile targets.
2. Add Android and iOS pipelines plus signing/export guidance.
3. Harden diagnostics, examples, and smoke tests.
4. Add CI strategy and onboarding documentation.
