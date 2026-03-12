# gdcpps

Godot CPP Scaffold.

This repository is the planned consumer-facing scaffold and build orchestration layer for Godot C++ projects that:

- use GDExtension for fast iteration in debug builds
- use a Godot module embedded into custom engine builds for release builds
- support Windows, Linux, macOS, Web, iOS, and Android
- let consumers choose engine feature sets per target

See `docs/SPEC.md`, `docs/USAGE.md`, `docs/PLAN.md`, and `docs/HOOKS.md` for the current design direction.

Current hook support is manifest-driven:

- `build.cpp_standard`
- `build.shared.extra_include_dirs`
- `build.shared.extra_source_globs`
- `build.debug.extra_include_dirs`
- `build.debug.extra_source_globs`
- `build.module.extra_include_dirs`
- `build.module.extra_source_globs`

Release/module builds place hooked external object files under the Godot build tree instead of beside the original source files.

Repo-local launchers are available as `gdcpps.bat` and `gdcpps.sh` in the repository root.
