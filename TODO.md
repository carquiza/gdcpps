# TODO

## Phase 0

- [x] Create initial repository skeleton for gdcpps.
- [x] Define the consumer project manifest format.
- [x] Decide on the Python entry point structure.
- [x] Define pinned Godot and godot-cpp version configuration files.
- [ ] Write migration notes from `gdcpp` to `gdcpps`.

## Phase 1

- [x] Implement `init` to generate a client project layout.
- [x] Add template files for sample C++ game code and Godot project content.
- [x] Generate module glue and debug GDExtension glue from project metadata.
- [x] Parameterize project names, module names, and output paths.

## Phase 2

- [x] Implement dependency sync for pinned Godot source.
- [x] Implement dependency sync for pinned godot-cpp.
- [x] Add host toolchain detection for Windows, Linux, macOS, Web, iOS, and Android.
- [x] Add validation for missing SDKs and unsupported target/host combinations.

## Phase 3

- [x] Implement Windows debug build.
- [x] Implement Windows release build with embedded module.
- [x] Implement Web debug build.
- [x] Implement Web release build with a size-first default profile.
- [x] Translate manifest feature selections into Godot SCons flags.

## Phase 4

- [ ] Implement Linux debug and release builds.
- [ ] Implement macOS debug and release builds.
- [ ] Validate platform-specific artifact naming and packaging.

## Phase 5

- [ ] Implement Android build pipeline.
- [ ] Implement iOS build pipeline.
- [ ] Document signing/export constraints for mobile targets.

## Phase 6

- [x] Add `doctor` diagnostics.
- [x] Add a sample project.
- [ ] Add automated end-to-end smoke tests.
- [ ] Add CI strategy documentation.
- [ ] Write consumer onboarding docs.
