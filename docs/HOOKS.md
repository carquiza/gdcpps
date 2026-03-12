# gdcpps Hooks Design

## Purpose

`gdcpps` needs a general way for consumer projects to bring in non-scaffold code without forking the tool or hand-patching generated build files after every run.

The immediate driver is monorepo use, where a Godot frontend project needs to compile repo-local engine or simulation code that lives outside `game/src`.

## Design Goals

- keep the default scaffold simple for normal users
- support monorepo and shared-code layouts without editing generated files
- keep debug GDExtension and release module builds aligned
- prefer declarative configuration over arbitrary shell hooks
- allow an escape hatch for rare cases that do not fit the declarative model

## Recommended Model

Use a two-layer hook system:

1. declarative manifest build inputs for common needs
2. an optional Python hook file for advanced or exceptional cases

The declarative layer should cover most projects. The Python layer should be explicitly secondary.

## Layer 1: Manifest Build Inputs

Add a `build:` section to `gdcpps.yaml` for reusable source and compiler settings.

Suggested shape:

```yaml
build:
  cpp_standard: c++20

  shared:
    include_dirs: []
    defines: []
    source_globs: []

  debug:
    include_dirs: []
    defines: []
    source_globs: []
    libs: []
    lib_dirs: []
    cxxflags: []
    linkflags: []

  module:
    include_dirs: []
    defines: []
    source_globs: []
    libs: []
    lib_dirs: []
    cxxflags: []
    linkflags: []
```

Phase 1 implemented fields:

- `build.cpp_standard`
- `build.shared.extra_include_dirs`
- `build.shared.extra_source_globs`
- `build.debug.extra_include_dirs`
- `build.debug.extra_source_globs`
- `build.module.extra_include_dirs`
- `build.module.extra_source_globs`

That is enough to solve the LockstepWorld monorepo case cleanly. The broader `include_dirs` / `defines` / `libs` shape remains the recommended direction for later expansion.

## Layer 2: Optional Python Hook File

For edge cases, allow a project-local Python file such as `gdcpps_hooks.py`.

Suggested entry points:

```python
def configure_debug(env, ctx) -> None:
    ...

def configure_module(env, ctx) -> None:
    ...
```

Suggested `ctx` fields:

- `project_root`
- `manifest`
- `platform`
- `mode`
- `module_name`
- `godot_cpp_dir`
- `godot_source_dir`

This hook should be allowed to mutate the SCons environment and return extra source files if needed.

## Why Not Arbitrary Shell Hooks

Shell hooks are a poor default for `gdcpps`.

- they are harder to validate
- they are less portable
- they create quoting and environment drift problems
- they make generated builds harder to reason about

If consumers need shell execution, it should be a later and more constrained feature, not the primary extension model.

## Generated Build Behavior

Both debug and module builds should consume the same resolved build-extension model.

That means:

- debug SConstruct generation reads `build.shared` and `build.debug`
- module `SCsub` generation reads `build.shared` and `build.module`
- common path resolution happens in one Python helper inside `gdcpps`
- relative paths resolve from the consumer project root

This avoids the current drift where debug generation lives in `scripts/build.py` while module customization only exists in project-local generated files.

## Platform Overrides

Platform-specific build inputs should come after the base model is stable.

Recommended future shape:

```yaml
platforms:
  windows:
    build:
      debug:
        lib_dirs: []
      module:
        lib_dirs: []
```

Do not start with this unless a real consumer needs it. The first implementation should stay small.

## Example: Monorepo Shared Simulation Code

```yaml
build:
  cpp_standard: c++20

  shared:
    extra_include_dirs:
      - ../src
    extra_source_globs:
      - ../src/core/**/*.cpp
      - ../src/sim/**/*.cpp

  debug:
    extra_include_dirs:
      - ../build/windows-debug/vcpkg_installed/x64-windows/include

  module:
    extra_include_dirs:
      - ../build/windows-debug/vcpkg_installed/x64-windows/include
```

This is the exact kind of workflow `gdcpps` should support natively.

## Implementation Plan

1. add a reusable manifest parser for build extensions
2. apply it to debug SConstruct generation
3. apply the same model to generated module `SCsub`
4. add schema validation and clear error messages
5. add an example project or test fixture that exercises extra source roots
6. add the optional Python escape-hatch hook only after the declarative path is stable

Steps 1 through 3 are now implemented for the first manifest hook surface.

## Documentation Updates Required

When implemented, update:

- `README.md`
- `docs/SPEC.md`
- `docs/USAGE.md`
- `docs/PLAN.md`
- `schema/README.md`

The docs should make it clear which fields are implemented now versus planned next.
