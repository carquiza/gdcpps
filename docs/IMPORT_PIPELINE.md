# Import Pipeline: Findings and Plan

## Problem Statement

gdcpps `pack.py` currently does a naive file walk of `project/`, packing raw source
assets (`.glb`, `.png`, etc.) into the PCK while skipping `.godot/imported/` entirely.
This diverges from Godot's standard export behavior and produces suboptimal release
builds.

## How Godot's Standard Export Works

Source: `editor/export/editor_export_platform.cpp` lines 1328-1512.

For every file in the project that has a `.import` sidecar, Godot's exporter:

1. Reads the `.import` file to get the `[remap] path` value, e.g.:
   ```
   path="res://.godot/imported/conveyor.glb-b9d9bc26f0a55e499d0939d165390989.scn"
   ```
2. Packs the **imported binary** (from `.godot/imported/`) into the PCK at that path.
3. Strips the `[deps]` and `[params]` sections from the `.import` file and packs the
   cleaned version.
4. Does **NOT** pack the raw source file (`.glb`, `.png`, etc.).

For files without a `.import` sidecar (`.tscn`, `.tres`, etc.), it packs them as-is
(with optional text-to-binary conversion).

### What a correct PCK contains

```
assets/models/conveyor.glb.import              <- cleaned [remap] only
.godot/imported/conveyor.glb-{hash}.scn        <- pre-baked PackedScene binary
assets/models/Textures/colormap.png.import     <- cleaned [remap] only
.godot/imported/colormap.png-{hash}.ctex       <- GPU-compressed CompressedTexture2D
project.godot                                  <- as-is
main.tscn                                      <- as-is
```

At runtime, `ResourceLoader::load("res://assets/models/conveyor.glb")` finds the
`.import` sidecar, follows the remap path, and loads the pre-baked binary directly.

## What gdcpps Currently Does

`pack.py` walks `project/`, skips `bin/` and `.godot/`, and packs everything else:

```
assets/models/conveyor.glb                     <- raw source GLB (dead weight)
assets/models/conveyor.glb.import              <- remap pointing to MISSING cache file
assets/models/Textures/colormap.png            <- raw source PNG (dead weight)
assets/models/Textures/colormap.png.import     <- remap pointing to MISSING cache file
project.godot                                  <- correct
main.tscn                                      <- correct
```

### Why it works anyway

When the runtime follows the `.import` remap to
`res://.godot/imported/conveyor.glb-{hash}.scn` and that path is missing from the PCK,
Godot falls back to loading the raw `.glb` via `ResourceFormatLoaderGLTF` (a runtime
loader that parses glTF on the fly). Similarly, `.png` files load via
`ImageFormatLoaderPNG`.

### Consequences of the current approach

| Issue | Impact |
|-------|--------|
| Raw source files are dead weight in the PCK | Larger download/install size |
| `.import` remaps point to missing files | Wasted lookup + fallback overhead on every load |
| No GPU texture compression (BCn/ASTC/ETC2) | Higher VRAM usage, slower GPU sampling |
| No import-time mesh optimization (LOD, tangents) | Lower rendering quality or runtime cost |
| GLB parsed at runtime instead of loading pre-baked `.scn` | Slower startup / load times |
| Fragile fallback behavior | May break on future Godot versions or on platforms without runtime loaders |

## Plan

### Step 1: Run Godot import before packing

Before `pack.py` collects files, invoke the built Godot executable (or a downloaded
headless editor) to populate `.godot/imported/`:

```
godot --import --headless --path <project_dir>
```

The `--import` flag (available since Godot 4.3) runs the editor's first-scan import,
waits for completion, then quits. It implies `--editor --quit`.

This should be integrated into `build.py`'s release flow, after the engine binary is
compiled but before packing. The built template executable itself cannot run `--import`
(it's not an editor build), so we need one of:

- **(a)** A downloaded Godot editor binary (matches the pinned version).
- **(b)** Building a headless editor as part of the release flow (expensive).
- **(c)** Running the import step using the debug GDExtension path: the user's locally
  installed Godot editor runs `--import --headless --path project/`.

Option **(c)** is the simplest and most practical: if the user has ever opened the
project in the editor (which they must have during development), `.godot/imported/`
already exists. The import step just ensures it's up to date.

Option **(a)** is better for CI where no editor may be installed. The `deps sync` step
could optionally download a headless editor binary alongside the source checkout.

### Step 2: Modify `pack.py` to follow `.import` remaps

Replace the naive file walk with import-aware logic:

```python
def collect_files(project_dir):
    files = []
    for path in walk(project_dir):
        if has_import_sidecar(path):
            # Read the .import file
            remap_path = parse_remap(path + ".import")
            # Pack the imported binary from .godot/imported/
            files.append(remap_path, full_path_for(remap_path))
            # Pack the cleaned .import file (strip [deps] and [params])
            files.append(path + ".import", cleaned_import(path + ".import"))
            # Do NOT pack the raw source file
        else:
            # Pack as-is (scenes, resources, config files)
            files.append(path, full_path_for(path))
    return files
```

Key behaviors:
- Parse `.import` files using a simple INI parser (already available in Python's
  `configparser`).
- Read `[remap] path` to find the imported binary.
- Strip `[deps]` and `[params]` sections from the `.import` before packing.
- Error if a remap target doesn't exist (import step wasn't run or failed).
- Continue to skip `bin/` directory.
- Continue to include `.godot/global_script_class_cache.cfg`.

### Step 3: Add `--skip-import` flag

For cases where the user has already run the import manually or wants to handle it
externally (CI with pre-cached imports):

```
gdcpps build release windows --skip-import
```

Default behavior: run import automatically before packing.

### Step 4: Validate and warn

- If `.godot/imported/` doesn't exist when packing, emit a clear error:
  `"Import cache missing. Run 'godot --import --headless --path project/' first, or remove --skip-import."`
- If any `.import` remap target is missing, fail with the specific file name.
- Print import stats: `"Packed 12 imported resources, 8 direct files (total: 20)"`

## File changes summary

| File | Change |
|------|--------|
| `scripts/pack.py` | Add `.import`-aware collection, remap following, `.import` cleaning |
| `scripts/build.py` | Add import step before packing in release flow |
| `scripts/gdcpps.py` | Add `--skip-import` CLI flag |
| `docs/USAGE.md` | Document the import step and `--skip-import` option |
| `docs/SPEC.md` | Add import pipeline to the release build specification |

## Edge Cases

- **Files with `importer="keep"`**: Pack the raw source file as-is (Godot's exporter
  does the same). This is used for files that shouldn't be converted.
- **Files with `importer="skip"`**: Exclude from the PCK entirely.
- **Platform-specific remap features** (`path.s3tc`, `path.etc2`): Godot's exporter
  selects the right path based on target platform features. gdcpps should select the
  `path` key (default) for now, with platform-specific selection as a future
  enhancement.
- **UID cache** (`.godot/uid_cache.bin`): Godot's exporter includes this. We should
  add it to `ALLOWED_PROJECT_DATA_FILES`.
- **Text-to-binary conversion**: Godot's exporter optionally converts `.tscn`/`.tres`
  to binary format during export. This is a nice-to-have optimization but not required
  for correctness.

## Testing

1. Build a release exe with the new import-aware packing.
2. Verify `ResourceLoader::load()` loads imported binaries (not raw fallback).
3. Compare PCK size before/after.
4. Compare startup time before/after.
5. Verify textures use GPU-compressed format (check VRAM usage in Godot profiler or
   via `RenderingServer::texture_get_format()`).
