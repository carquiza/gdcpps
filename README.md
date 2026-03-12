# gdcpps

Godot CPP Scaffold.

This repository is the planned consumer-facing scaffold and build orchestration layer for Godot C++ projects that:

- use GDExtension for fast iteration in debug builds
- use a Godot module embedded into custom engine builds for release builds
- support Windows, Linux, macOS, Web, iOS, and Android
- let consumers choose engine feature sets per target

See `docs/SPEC.md`, `docs/USAGE.md`, and `docs/PLAN.md` for the initial design.

Repo-local launchers are available as `gdcpps.bat` and `gdcpps.sh` in the repository root.
