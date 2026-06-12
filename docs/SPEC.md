# gdcpps Specification

## Summary

gdcpps is a scaffold and superbuild system for Godot C++ projects that need two things at once:

- fast debug iteration through GDExtension
- optimized release distribution through a custom Godot engine build with project code compiled as a Godot module

The intent is to replace the current copy-template workflow with a generated client project and a pinned, reproducible engine build pipeline.

## Goals

- Support these output platforms:
  - Windows
  - Linux
  - macOS
  - Web
  - iOS
  - Android
- Keep the embedded-module release path as the primary distribution model.
- Let consumers control Godot feature inclusion and stripping per target.
- Provide a small default Web profile.
- Make project creation reproducible and less finicky than manually wiring Godot, module layout, pack embedding, and platform toolchains.
- Keep source version pinning explicit for Godot and godot-cpp.

## Non-Goals

- Normal package-manager style consumption such as `vcpkg install gdcpps` followed by direct linking from an arbitrary host project.
- Hiding all platform complexity. The system should make platform requirements explicit and reproducible, not pretend they do not exist.
- Supporting arbitrary Godot versions simultaneously in the first phase.

## Product Model

gdcpps is not a library package. It is a scaffold plus build orchestrator.

It has three responsibilities:

1. Create a consumer project layout.
2. Materialize pinned engine dependencies.
3. Build debug and release outputs for the selected target and feature set.

## Core Concepts

### 1. Generated Client Project

A consumer does not copy the whole repository manually. Instead, gdcpps creates a project workspace with:

- a game source area
- a Godot project content area
- a manifest describing engine version, targets, and feature profiles
- generated build glue for GDExtension debug and embedded-module release

### 2. Pinned Superbuild

Release builds must compile against Godot source with `custom_modules`, so the real build root is the Godot source tree.

To make that stable, gdcpps owns:

- the exact Godot revision or tag
- the exact godot-cpp revision or branch needed for debug builds
- the scripts that materialize those dependencies into a known layout
- the mapping from consumer feature choices to Godot SCons flags

### 3. Feature Manifest

Consumers configure engine features through a manifest rather than by editing `custom.py` directly.

The manifest will support:

- platform-specific overrides
- named profiles such as `web-small`, `desktop-default`, and `mobile-default`
- explicit enable and disable lists for Godot modules and features
- validation of incompatible combinations
- build-extension inputs for shared code, include roots, and compile settings

## Build Modes

### Debug Mode

Debug mode builds the game code as a GDExtension against `godot-cpp`.

Properties:

- fast iteration
- editor/runtime launched against the generated client project
- stable client-facing development workflow
- no custom engine rebuild for typical code changes

### Release Mode

Release mode builds Godot from source with the consumer game code compiled as a module.

Properties:

- standalone shipping artifacts
- per-target engine feature stripping
- optional PCK embedding where the platform format supports it
- larger build cost but better size/control

## Supported Targets

Initial target matrix for gdcpps:

| Target | Debug | Release | Notes |
|---|---|---|---|
| Windows | Yes | Yes | First-class early target |
| Linux | Yes | Yes | First-class early target |
| macOS | Planned | Yes | Requires Apple toolchain validation |
| Web | Yes | Yes | Default profile should favor small size |
| iOS | Planned | Yes | Requires Xcode and signing workflow design |
| Android | Planned | Yes | Requires SDK/NDK integration and packaging |

In early milestones, support means the scaffold has an explicit preset and documented toolchain checks. A target is not considered supported just because Godot itself can build it.

## Consumer Configuration

A generated project will contain a manifest file. The initial expected fields are:

```yaml
project:
  name: mygame
  godot_version: 4.5.1
  module_name: mygame

debug:
  editor_binary: auto

profiles:
  base: desktop-default
  web: web-small
  ios: mobile-default
  android: mobile-default

features:
  enable: []
  disable:
    - gdscript
    - advanced_gui

platforms:
  web:
    disable:
      - physics_2d
      - physics_3d
      - navigation_2d
      - navigation_3d
  windows:
    enable:
      - physics_3d
```

This file is a source of truth for generated `custom.py` or equivalent build flags.

## Build Extension Hooks

Consumer projects sometimes need more than `game/src`.

The recommended `gdcpps` extension model is:

1. declarative build inputs in the manifest for extra include directories, source globs, defines, libraries, and compiler settings
2. an optional Python hook file only for cases that do not fit the declarative model

This keeps the common path inspectable and portable while still allowing advanced users to extend the generated SCons environment.

The intended detailed design lives in `docs/HOOKS.md`.

Currently implemented manifest fields are:

- `build.cpp_standard`
- `build.shared`, `build.debug`, and `build.module`, each supporting
  `extra_include_dirs`, `extra_source_globs`, `defines`, and `cxxflags`
- the same fields under `platforms.<platform>.build.shared|debug|module`

## Planned User Experience

The intended commands are:

```text
gdcpps init mygame
gdcpps deps sync
gdcpps build debug windows
gdcpps build release web --profile web-small
gdcpps build release android
gdcpps run debug windows
```

The first implementation may begin with Python scripts instead of an installed CLI, but the UX should converge on a single entry point.

## Repository Layout

Planned repository layout:

```text
gdcpps/
  docs/
    SPEC.md
    USAGE.md
    PLAN.md
  scaffold/
    templates/
    defaults/
  scripts/
    gdcpps.py
    init.py
    deps.py
    build.py
    run.py
    doctor.py
  profiles/
    web-small.py
    desktop-default.py
    mobile-default.py
  schema/
    project.example.yaml
  examples/
    spinning_cube/
```

## Architecture Decisions

### Scaffold Rather Than Package Manager

A normal package manager does not fit the release model because embedded-module builds are not standalone library consumption. They require a custom engine build rooted in Godot source.

### Manifest Rather Than Hand-Edited SCons Profiles

Consumers need feature control, but hand-editing raw Godot build flags is easy to get wrong. A higher-level manifest will be easier to validate and document.

### Explicit Version Pinning

Godot internals and godot-cpp compatibility are version-sensitive. gdcpps will treat version pinning as a core part of the product, not an optional convenience.

### Platform Presets

Web, mobile, and desktop have different tradeoffs. Starting from known presets is safer than exposing a flat pile of raw toggles.

## Web-Small Baseline

The initial Web baseline should:

- optimize for size
- disable threads unless explicitly requested
- disable dynamic linking
- disable features not needed by the consumer project
- prefer a minimal runtime profile with consumer opt-ins

Likely defaults:

- `target=template_release`
- `optimize=size`
- `lto=full`
- `threads=no`
- `dlink_enabled=no`
- GDScript disabled by default for release unless consumer opts in
- advanced GUI disabled by default
- physics/navigation disabled by default until requested

## Risks

- iOS and Android packaging will require more than pure compilation; signing/export workflows need explicit design.
- Godot feature flags interact in non-obvious ways, so validation must be part of the build tool.
- Consumers will expect deterministic behavior across machines, so dependency acquisition and toolchain checks must be rigorous.
- The debug and release integration paths are different enough that generated layouts must avoid accidental drift between them.
- If debug and module build extensions are configured differently, consumers can accidentally ship code that was never exercised in debug.

## Milestones

1. Define scaffold layout and manifest schema.
2. Build Windows and Web end-to-end from the new scaffold.
3. Add Linux and macOS presets.
4. Add iOS and Android presets plus packaging guidance.
5. Harden validation, docs, and example projects.
