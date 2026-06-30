# gdcpps

Godot CPP Scaffold.

This repository is the planned consumer-facing scaffold and build orchestration layer for Godot C++ projects that:

- use GDExtension for fast iteration in debug builds
- use a Godot module embedded into custom engine builds for release builds
- support Windows, Linux, macOS, Web, iOS, and Android
- let consumers choose engine feature sets per target

See `docs/SPEC.md`, `docs/USAGE.md`, `docs/PLAN.md`, and `docs/HOOKS.md` for the current design direction.

Implemented build targets: Windows, Linux, macOS, and Web (debug and release). iOS and Android are planned. macOS release builds ship the engine binary alongside a sidecar `.pck`; a signed `.app` bundle is a planned publish step.

Current hook support is manifest-driven:

- `build.cpp_standard`
- `build.shared`, `build.debug`, and `build.module` sections, each supporting
  `extra_include_dirs`, `extra_source_globs`, `defines`, and `cxxflags`
- the same fields under `platforms.<platform>.build.shared|debug|module`,
  merged after the top-level sections for the active target platform

Release/module builds place hooked external object files under the Godot build tree instead of beside the original source files.

Repo-local launchers are available as `gdcpps.bat` and `gdcpps.sh` in the repository root.

## Testing

Unit tests live in `tests/` and need only the standard library (manifest-loading tests additionally need PyYAML):

```text
python -m unittest discover -s tests
```

GitHub Actions (`.github/workflows/ci.yml`) runs the tests plus an `init`/`render-profile`/`doctor` smoke pass on Windows, Linux, and macOS. Engine builds are out of CI scope for now.
