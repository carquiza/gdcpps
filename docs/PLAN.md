# gdcpps Plan

## Objective

Build a reliable scaffold and superbuild system for Godot C++ projects that preserves embedded-module release builds while making project creation and per-target feature control reproducible.

## Phase 0: Design Baseline

Deliverables:

- project specification
- planned user workflow
- initial task backlog
- repository skeleton

Exit criteria:

- architecture written down
- target matrix defined
- consumer configuration model defined at a high level

## Phase 1: Scaffold Core

Deliverables:

- project initializer
- generated client directory layout
- manifest file format
- minimal template assets

Key decisions:

- choose Python entry point layout
- choose manifest format
- define generated filenames and module naming rules

Exit criteria:

- `init` creates a usable project skeleton without manual edits

## Phase 2: Dependency Sync

Deliverables:

- pinned Godot version config
- pinned godot-cpp version config
- dependency sync script
- host toolchain checks

Exit criteria:

- a fresh machine can materialize required source dependencies deterministically

## Phase 3: Windows and Web End-to-End

Deliverables:

- debug build flow for Windows and Web
- release build flow for Windows and Web
- generated feature profile translation into Godot build flags
- project pack/embed flow for supported targets

Exit criteria:

- sample project builds and runs on Windows and Web from the new scaffold

## Phase 4: Desktop Expansion

Deliverables:

- Linux support
- macOS support
- platform presets and validation rules

Exit criteria:

- sample project builds for all desktop targets using the same scaffold model

## Phase 5: Mobile Expansion

Deliverables:

- iOS preset and toolchain checks
- Android preset and toolchain checks
- packaging/export guidance for both platforms

Exit criteria:

- documented, repeatable mobile builds from the scaffold

## Phase 6: Hardening

Deliverables:

- validation and diagnostics
- clearer error messages
- example project
- CI strategy
- migration guidance from the current gdcpp template
- reusable build-extension hooks for monorepo and shared-code layouts

Exit criteria:

- consumer workflow is documented, testable, and stable enough for wider use

## Implementation Priorities

1. Manifest schema and repository layout
2. Bootstrap/init
3. Dependency sync
4. Windows/Web build path
5. Feature profile generation
6. Linux/macOS
7. iOS/Android
8. Generalized manifest-driven build hooks for extra source roots and compiler settings
