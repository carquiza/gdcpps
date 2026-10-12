# STATUS

**Updated:** 2026-10-12 · **Phase:** maintenance (build/run for client projects) · **Health:** One open defect in `run`

## Now / Next
1. **Fix: `gdcpps run debug` forwards game arguments as Godot engine flags.** Found running
   asset-flip on macOS (any platform is affected). `./gdcpps.sh run debug macos -- --mute --script f.txt`
   launches `Godot --path <project> --mute --script f.txt`; Godot takes `--script` as its own flag
   (run a GDScript) and exits with status 1, so the game never sees its args. A second `--` does not
   help: it is stripped too. Cause: `_game_args` (`scripts/run.py:56`) drops the leading `--`, and
   the debug command (`scripts/run.py:97`) appends the args right after `--path`. Godot needs a
   `--` before user args (they reach the game via `OS.get_cmdline_user_args()`). Fix: insert `"--"`
   between `--path <project>` and the game args when there are any; check the release path
   (`scripts/run.py:106`, the exported binary) the same way; add a case to `tests/test_cli.py`.
   Workaround in asset-flip: `play.sh` calls Godot directly.
2. **`init` should gitignore `.gdcpps/`.** Everything in it is per machine: `deps sync` writes
   `state/deps.json` with absolute paths, and every build rewrites `generated/` (also absolute
   paths). asset-flip tracked it from its first commit, so each build on another machine showed
   it modified; it is now ignored there (2026-10-10). Have `init` write a `.gitignore` with
   `.gdcpps/` (and `deps/`), and drop the stale `.gdcpps/README.txt` scaffold text.

Roadmap and phase checklist: `TODO.md`.

## Recently done
- 2026-10-12 — **Android release builds** (`scripts/android.py`, `tests/test_android.py`): arm64 engine
  with the module (scons installs the pinned NDK), `gradlew generateGodotTemplates` for the template
  APK, an "Android" preset (arm64 only, icon), editor export signed with Godot's debug keystore or a
  manifest keystore (password via an env var, passed as `GODOT_ANDROID_KEYSTORE_RELEASE_*`); `run
  release android` installs with adb and starts `GodotApp`. Preset editing moved to
  `scripts/export_presets.py` (shared with iOS). Verified with asset-flip on a Galaxy S20 FE.
- 2026-10-12 — **iOS release builds** (`scripts/ios.py`, `tests/test_ios.py`): `build release ios`
  builds the arm64 engine library with the module (Metal, no MoltenVK), the Xcode template zip, an
  "iOS" export preset from `platforms.ios.export`, exports with the editor, and signs a `.app` with
  xcodebuild; `run release ios` installs and launches it with devicectl. Verified with asset-flip on an
  iPhone 14 Pro (Xcode 27). Notes: Xcode 26+ needs min iOS 15.0 (preset default); full LTO makes the
  final Xcode link slow (~20 min on an A18 Pro Mac); no iOS debug build.
- (earlier) macOS build/run support and local source-tree deps sync (`f71d687`); `run` forwards
  arguments after `--` (`3cefc37`).

## Blockers
None.

## Pointers
- CLI entry: `scripts/gdcpps.py`; run: `scripts/run.py`; build: `scripts/build.py`.
- Uncommitted local edits (2026-10-10, not from this note): `scripts/build.py`, `scripts/init.py`,
  `scripts/run.py`, `tests/test_cli.py`.
