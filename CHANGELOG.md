# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(pre-1.0: minor versions may include breaking changes).

## [0.1.0] - Milestone 1: Linux Core Skeleton

### Added

- Project skeleton: `pyproject.toml` (hatchling build), `src/unren` package layout,
  `unren` console-script entry point (`unren.cli:main`), `python -m unren` support.
- `unren.core`: shared dataclasses/utilities — `GameContext`, `PythonRuntime`,
  `RenPyVersionInfo`, `ArchiveInfo` (`core.context`); path resolution helpers
  (`core.paths`); TOML config loading with `unren.toml`/`.unren.toml` discovery
  (`core.config`); structured error hierarchy (`core.errors`); a generic
  success/failure `Result` type with JSON-safe serialization (`core.result`).
- `unren.detection.renpy`: the upstream `detect_renpy_version.py` 7-step priority
  cascade (live `import renpy` → `script_version.txt` → `renpy/version.py` →
  `.rpyc`/`.rpymc` magic bytes → `.rpa` archive header → heuristic text-file regex
  scan → hard `UNKNOWN` failure). Fail-closed: never guesses a generation.
- `unren.detection.python`: Python runtime resolver — prefers a suitable system
  Python 3 interpreter (>= 3.8), falls back to a Ren'Py-bundled interpreter under
  `<root>/lib/**`, otherwise reports unresolved.
- `unren.detection.archives`: archive format detection — live `renpy.loader`
  introspection, on-disk header content-sniffing (RPA-1.0/2.0/3.0/3.2, RPAN-3.0,
  ZiX-12A/12B, SVAC-1.0, RWA-3.0), hardcoded `.rpa` fallback; plus a general
  archive-file finder used by `detect`/`doctor` reporting.
- `unren.detection.game`: ties the above together into `detect_game()` /
  `require_game()`, locating a plausible game root by walking up to 6 levels for
  `game/`/`renpy/`/`lib/` markers.
- `unren.cli`: argparse-based CLI with global options (`--dry-run`, `--verbose`,
  `--quiet`, `--json`, `--no-color`, `--output`, `--config`) and two fully
  implemented subcommands:
  - `unren detect [PATH]` — human-readable or `--json` game detection report.
  - `unren doctor [PATH]` — OS info, game detection summary, Python runtime,
    archive formats present, and external tool availability (`7z`, `p7zip`,
    `git`), as text or `--json`.
  - `extract`, `decompile`, `console`, `devmode`, `all` subcommands are
    registered but stubbed (exit code 3, "not yet implemented") — real logic is
    scheduled for Milestone 2+.
- `unren.ui.output`: minimal text/JSON output formatting, with optional `rich`
  support (falls back to plain `print`/`sys.stderr` if `rich` isn't installed).
- Packaging: LICENSE (GPLv3, matching upstream), README with attribution to
  `Lurmel/UnRen-forall`, install/quickstart docs, and this changelog.
- Test suite: unit tests for `core.paths`, the Ren'Py version-string parsers and
  detection cascade, archive header sniffing, and Python runtime resolution;
  integration tests invoking the real CLI (`unren.cli.main`) end-to-end against
  synthetic Ren'Py 6/7/8-style fixtures under `tests/fixtures/`.

### Known limitations (by design, this milestone)

- No extraction, decompilation, or game-patching actions yet.
- No interactive UI (bare `unren`/`unren PATH` with no subcommand just prints help).
- Archive *extraction* logic (RPA reader) is not implemented — only detection/reporting.

## [Unreleased] - Milestone 2: RPA Extraction

### Added

- `unren.adapters.rpatool`: from-scratch, version-pinned RPA container reader
  (RPA-1.0/.rpi, RPA-2.0, RPA-3.0, RPA-3.2). Reimplements the publicly
  documented container format (pickle+zlib index, XOR-obfuscated v3/v3.2
  offsets) directly against `shizmob/rpatool`'s reference source and the
  Ren'Py RPA format reverse-engineering wiki — no undocumented vendor blob,
  no `rpatool` PyPI dependency (it isn't published there). Read-only:
  container/index parsing and member extraction only, no create/append/delete.
  Formats detected but not (yet) supported for extraction (RPAN-3.0, ZiX-12A/
  12B, SVAC-1.0, RWA-3.0 "neutron" archives) raise a clear
  `UnsupportedArchiveFormatError` instead of mis-parsing.
- `unren.core.backup`: centralized `.unren/backups/<relative-path>` backup
  helper used by mutating actions before any overwrite.
- `unren.actions.extract_rpa`: `unren extract` action — discovers archives
  (reusing Milestone 1's `unren.detection.archives`), builds a full
  extraction plan (per-archive/per-member destinations + conflict list), then
  executes it. Output management: default `unren-extracted/` sibling folder,
  `--output PATH` override, `--in-place` (extract into `game/`, explicit
  opt-in only). Overwrite protection: any existing destination file aborts
  that archive's extraction with a clear error unless `--force` is given,
  which backs up the existing file first. `--dry-run` (global flag) computes
  and reports the full plan without writing or creating anything.
- `unren extract [PATH] [--output PATH] [--in-place] [--force]` wired into
  the CLI (text and `--json` output), replacing the Milestone 1 stub.
- Test suite: `tests/helpers/rpa_builder.py` (synthetic RPA v1/v2/v3/v3.2
  fixture builder — no real, potentially copyrighted archives needed), unit
  tests for the rpatool adapter (round-trip extraction per format, unicode/
  space member names and paths, corrupt/unsupported-format error handling),
  and CLI integration tests for `extract` (default output dir, `--output`,
  `--dry-run` no-op guarantee, `--json`, overwrite protection, `--in-place`,
  RPA-2.0/3.0 parity, unicode/space game-directory paths, "no archives found").

### Known limitations (by design, this milestone)

- Only the "standard" RPA family (v1/2/3/3.2) is supported for extraction.
  The `altrpatool` fallback (importing a game's own bundled `renpy.loader` to
  read non-standard/obfuscated headers) and the neutron formats
  (RPAN-3.0/ZiX-12A/12B/SVAC-1.0/RWA-3.0) are out of scope for this
  milestone — detected and reported, but extraction is refused with a clear
  error rather than guessed at.
- No RPYC decompilation or game-patching actions yet (Milestone 3+).

## [Unreleased] - Milestone 4: Remaining UnRen Features

### Added

- `unren.core.game_patch`: shared helper for the whole family of upstream
  actions that write one small, static, idempotent `.rpy` file into `game/`
  and skip (no-op) if it already exists (`docs/UPSTREAM-BEHAVIOR.md` §5).
  Centralizes the "check-before-write, never overwrite the marker" mechanism
  used by every action below instead of duplicating it five times.
- `unren.actions.enable_console` / `unren console enable [PATH]`: writes
  `game/unren-console.rpy` (`config.console = True`, `config.developer = True`),
  1:1 parity with upstream `:console` (`ACT.a`). **MUST**.
- `unren.actions.enable_devmode` / `unren devmode enable [PATH]`: writes
  `game/unren-debug.rpy` (`config.debug = True`), 1:1 parity with upstream
  `:debug` (`ACT.b`). **MUST**.
- `unren.actions.game_patches` (`unren <name> enable [PATH]` for each):
  - `skip` → `game/unren-skip.rpy` — force-skip seen dialogue (`:skip`, `ACT.c`). **MUST**.
  - `skipall` → `game/unren-skipall.rpy` — force-skip incl. unseen + disabled
    transitions (`:skipall`, `ACT.d`). **MUST**.
  - `rollback` → `game/unren-rollback.rpy` — force-enable rollback with a
    256-entry history buffer, neutralizes `renpy.block_rollback` (`:rollback`,
    `ACT.e`). **MUST**.
  - `quicksave` → `game/unren-quicksave.rpy` — bind F5/F9 to QuickSave/
    QuickLoad (`:quick`, `ACT.f`). **SHOULD**.
  - `quickmenu` → `game/unren-qmenu.rpy` — force the quick-menu overlay always
    visible (`:qmenu`, `ACT.g`). **SHOULD**.
  - `nosync` → `game/unren-nsync.rpy` — disable Ren'Py's cross-device
    save-sync (`:nasty_sync`, `ACT.n`; kept as a generically useful toggle on
    Linux even though the upstream OneDrive-conflict motivation doesn't
    directly apply). **SHOULD**.
- `unren.actions.cleanup` / `unren cleanup restore|delete [PATH]`: restore or
  permanently delete files under the centralized `.unren/backups/` tree
  (Milestone 2's `unren.core.backup` scheme). Semantic (not byte-for-byte)
  parity with upstream `:restore_files`/`:delete_backups` (`ACT.r`/`ACT.s`)
  — see module docstring for the deliberate, documented deviation from
  upstream's flat `.org`-suffix convention. `delete` is irreversible and
  requires `--yes` (unless `--dry-run`) — the one destructive action in this
  whole family, gated behind explicit confirmation per the parity matrix's
  own note. Both operations treat "nothing to do" as success (exit 0),
  intentionally *not* reproducing upstream's own `:delete_backups` vs.
  `:restore_files` exit-code inconsistency (documented in
  `docs/UPSTREAM-BEHAVIOR.md` §7.4). **MUST**.
- `unren.actions.run_all` / `unren all [PATH] [--force]`: runs every
  implemented non-destructive action in a fixed, safety-ordered sequence
  (detect → extract → decompile → console/devmode → skip/rollback/quicksave/
  quickmenu/nosync), matching the task card's required ordering. Every
  stage's outcome (ok/skipped/failed) is recorded in the report even when an
  earlier stage fails or a later stage is structurally skipped (e.g.
  decompile skipped on unknown Ren'Py generation) — fail-closed, no silent
  skip. Deliberately excludes `cleanup restore`/`cleanup delete` (destructive/
  irreversible operations don't belong in a bulk "apply everything" command).
- `unren.core.errors`: `MissingGameDirectoryError` (a patch action was asked
  to write into a `game/` dir that doesn't exist) and
  `ConfirmationRequiredError` (an irreversible action was requested without
  explicit confirmation).
- CLI wiring for all of the above, with `--json` output and `--dry-run`
  support throughout, consistent with `extract`/`decompile`'s existing
  contract.
- Test suite: unit tests for `core.game_patch`, `enable_console`,
  `enable_devmode`, `game_patches` (parametrized across all six actions),
  `cleanup` (restore/delete, confirmation gating, dry-run, "nothing to do"),
  and `run_all` (stage ordering, unknown-generation skip, missing-game-dir
  skip, dry-run, idempotency); CLI integration tests for every new
  subcommand (marker-file content, idempotency, `--json`, `--dry-run`,
  `cleanup restore`/`cleanup delete --yes` round-tripping real backups from
  `extract --force`, and `unren all` end-to-end).

### Known limitations (by design, this milestone)

- Addon installers (Universal Gallery Unlocker, Universal Choice Descriptor,
  Universal Transparent Text Box, 0x52_URM, custom add-on installer),
  `replace_anyname` (character-name replacement), `extract_text` (Ren'Py
  native translate-stub scaffolding), the `altrpatool`/"with key" extraction
  fallback, and WOS SHIELD pre-decrypt remain out of scope — all SHOULD/COULD
  priority per the parity matrix, not MUST, and each has its own
  network-dependency, external-tool-dependency, or fixture-availability risk
  flagged in `docs/UPSTREAM-BEHAVIOR.md` §5 warranting separate follow-up
  milestones rather than being folded into this one.
- No interactive UI (bare `unren`/`unren PATH` still just prints help;
  Milestone 5).
- Context-menu registry integration and self-update remain explicit
  non-goals on Linux (`docs/UPSTREAM-BEHAVIOR.md` §3).

## [Unreleased] - Milestone 6: Packaging

### Added

- `pyproject.toml` `[project.scripts]` entry point (`unren = "unren.cli:main"`)
  already present from Milestone 1 verified end-to-end as the packaging
  target for this milestone: confirmed working via `pipx install <repo>` and
  a `uv pip install`-into-isolated-venv equivalent of `uv tool install
  <repo>` (both produce a global `unren` command with no repo-checkout
  dependency at runtime; `unren --version`/`unren doctor` run correctly from
  an unrelated directory such as `/tmp`).
- `packaging/arch/PKGBUILD`: Arch/CachyOS pacman package definition. Builds
  the wheel via `python -m build` (`makedepends`: `python-build`,
  `python-installer`, `python-wheel`, `python-hatchling`), runs the full
  pytest suite as `check()` (`checkdepends`: `python-pytest`,
  `python-pytest-cov`) with `PYTHONPATH` pointed at `src/` (the package isn't
  installed yet at check-time), and installs the built wheel via `python -m
  installer --destdir` in `package()`. Declares `depends=(python
  python-rich python-platformdirs)` (matches this project's `ui`/`paths`
  extras, which are runtime-required for the full experience rather than
  optional on Arch) and `optdepends` for `7zip`/`git` (surfaced by `unren
  doctor`) and AUR-only `python2` (legacy unrpyc variant fallback).
  Builds directly from the local repo checkout (`source=()` is empty,
  `_repo_root="$startdir/../.."`) rather than a tagged release tarball, since
  this project does not yet publish signed upstream release archives.
- README: Arch/CachyOS `makepkg -si` install instructions alongside the
  existing `pipx`/`uv tool` section; expanded status/roadmap notes for
  Milestones 5-6.

### Verified

- `uv build` produces a wheel whose `RECORD`/`entry_points.txt` matches the
  declared `[project.scripts]` entry point; `pipx install /path/to/repo`
  installs cleanly and `unren --version`/`unren doctor` (run from `/tmp`,
  no repo access) both succeed.
- `packaging/arch/PKGBUILD` produces a valid `.SRCINFO` (`makepkg
  --printsrcinfo`); its `build()`/`check()`/`package()` steps were
  independently reproduced against a venv provisioned with the exact
  package set Arch's `pacman` would install for this PKGBUILD's
  `depends`/`makedepends`/`checkdepends` (the execution sandbox used to build
  this milestone has no interactive `sudo`, so `makepkg -si`'s own `pacman
  -S` dependency-install step could not be run end-to-end here; the
  equivalent pip-based dependency set was verified to produce the same
  build/check/package outcomes instead). Full test suite (297 tests) passes
  in this reproduction.
- Scope note: this milestone's distribution target was narrowed to
  Arch/CachyOS only (operator directive during execution) — Debian/Ubuntu/
  Fedora packaging is explicitly out of scope and was not implemented or
  tested.

### Known limitations (by design, this milestone)

- `makepkg -si`'s dependency-installation step (`pacman -S` for
  `makedepends`/`checkdepends`) requires interactive `sudo` and was not
  exercised end-to-end in the execution environment used to build this
  milestone (no passwordless sudo available); build()/check()/package() were
  verified directly instead (see above). A real Arch/CachyOS machine with
  working `sudo` should run `makepkg -si` cleanly per the README instructions.
- No AUR submission / package signing in this milestone - the PKGBUILD is
  provided for local `makepkg` builds from a repo checkout, not yet published
  to the AUR.

## [0.1.0] - Milestone 7: Release Candidate

### Scope note (operator directive)

This milestone's distribution/compatibility matrix was narrowed to
**Arch/CachyOS only**, consistent with M6's own scope narrowing -
Debian/Ubuntu/Fedora matrix testing is explicitly out of scope for this
release and was not implemented or tested. Ren'Py 6/7/8 generation coverage
and the edge-case/error-determinism acceptance criteria are unaffected by
this narrowing and were fully verified.

### Fixed

- **Bugfix: unhandled `PermissionError`/`OSError` crash on read-only
  filesystems.** Every mutating action (`console enable`, `devmode enable`,
  the `skip`/`skipall`/`rollback`/`quicksave`/`quickmenu`/`nosync` family,
  `extract` without `--dry-run`) previously let a raw Python traceback
  escape `unren.cli.main()` whenever the target filesystem refused a write
  (e.g. a read-only `game/` directory, a read-only mount, or a destination
  directory `extract` couldn't `mkdir()` into) - a silent-fail-adjacent
  crash that violated this project's own "deterministic error behavior,
  never a crash" acceptance bar. `main()` now catches any `OSError` that
  escapes command dispatch and reports it through the same structured
  `UnrenError`/`Result` contract every other error already uses (new
  `filesystem-error` error code), with a translated human-readable message
  and a matching `--json` error shape, exit code 1 either way. Verified with
  both a real `chmod 555` read-only `game/` dir (patch-action write path)
  and a real read-only game root (`extract`'s default-output-dir `mkdir()`
  path) - both now report a clean structured error instead of a traceback.

### Verified

- **CI/CD test matrix**: `.github/workflows/ci.yml` added - `pytest` job
  (matrix: system Python + a pinned Python 3.10 leg) and a `pkgbuild` job
  (`makepkg --printsrcinfo` + full unprivileged `makepkg -s` build/check),
  both running inside the official `archlinux:base-devel` container image
  (no native Arch GitHub-hosted runner exists, so a real Arch userland
  inside a container is the standard substitute - not a stand-in for a
  different distro). Independently reproduced locally against a fresh
  `archlinux:base-devel` Docker container (not just written and assumed
  correct): full `pytest tests/` (304 tests) passed inside the container;
  `makepkg -s --noconfirm --nosign` as an unprivileged user completed
  build()/check()(304 passed)/package() successfully; the resulting
  `.pkg.tar.zst` was installed via `pacman -U` and `unren --version`/`unren
  doctor` both ran correctly from `/tmp` afterward - a fuller end-to-end
  reproduction than M6 could achieve (M6's sandbox had no interactive
  `sudo` for the `pacman -S`/root-build step; this pass used a container
  instead and completed the entire build/install/run cycle for real).
- **Ren'Py 6/7/8 generation matrix**: exercised via the existing
  `tests/fixtures/renpy6_game`/`renpy7_game`/`renpy8_game` synthetic
  fixtures (all milestones' test suites) plus M3.5's independent
  real-SDK/real-testcase verification pass (`docs/UNRPYC-COVERAGE.md`, 77
  real `.rpyc` files across all three generations, zero failures) - no new
  gaps found, no changes needed this milestone.
- **Edge cases**: 7 new integration tests added
  (`tests/integration/test_release_candidate_edge_cases.py`) covering
  read-only-filesystem determinism (the bugfix above, both text and
  `--json` output), a nonexistent target path (`doctor` reports
  `game_found: false` with a clear `detection_error`, exit 0, no crash), an
  unknown/undetectable Ren'Py generation (`doctor` reports
  `renpy_generation: "unknown"`; `decompile` refuses with a clear
  `runtime-resolution-error` reason rather than guessing a decompiler
  variant), matching the project's existing coverage for unicode/space-in-path
  archive members and paths (`test_rpatool_adapter.py`,
  `test_extract_paths_with_spaces_and_unicode`) and corrupt/unrecognized
  RPA/RPYC containers (`test_rpatool_adapter.py`'s
  `test_corrupt_index_raises_corrupt_archive_error`,
  `test_decompile_unknown_format_reported_as_error_not_skipped`) which were
  already green and needed no changes. Full suite: 304/304 passed
  (`.venv/bin/python -m pytest tests/ -q`).
- **`--dry-run` reliability**: new regression test confirms `extract
  --dry-run` against a `chmod 555` read-only game root computes and reports
  the full plan (exit 0) with zero filesystem changes (byte-for-byte
  directory-listing diff before/after) - it never needs to write anything,
  so it structurally cannot be broken by a read-only mount.
- **Performance**: a synthetic 1000-member / ~4 MB RPA archive extracted via
  the full CLI path (`unren --json extract`) in ~0.15s wall-clock on the
  verification host - no scaling concern found for typical Ren'Py game
  archive sizes.
- **Python-2 legacy path**: no code changes this milestone. M3.5's
  dedicated verification (`docs/UNRPYC-COVERAGE.md`) already confirmed
  `unrpyc_current` alone covers all three Ren'Py generations without a
  Python 2 runtime, with the vendored `unrpyc_legacy` (real Python 2, v1.3.2)
  kept as a documented, still-functional fallback (confirmed then via a
  real `pyenv`-provisioned Python 2.7.18 interpreter) for the one narrow
  gap (~genuine untouched Screen Language 1 source) `unrpyc_current` can't
  parse. That milestone's own re-verification checklist re-confirmed here:
  status unchanged, explicitly documented, not a defect.

### Known limitations (by design, this milestone)

- Debian/Ubuntu/Fedora are explicitly out of scope for this release (scope
  narrowed to Arch/CachyOS by operator directive during M6/M7) - not tested,
  not a defect.
- CI does not install a real Ren'Py SDK (large download, no additional
  coverage beyond the fixture-based + M3.5 real-file verification already
  in place) - see `docs/UNRPYC-COVERAGE.md` for that separate, manual,
  real-SDK verification pass.

## [Unreleased] - Menu enhancement: cwd auto-detect on bare `unren`

### Changed

- Bare `unren` (no subcommand, no path) now inspects the current working
  directory before opening the interactive menu (`unren.ui.interactive`):
  - cwd directly contains both `game/` and `renpy/` (recognized Ren'Py
    game) -> the menu opens directly for that directory, same as before.
  - cwd is not recognized -> prints a translated error ("No Ren'Py game
    detected in current directory. Please specify a game path: unren
    /path/to/game" / German equivalent) and exits non-zero, instead of
    opening the menu.
  - `unren <path>` (an explicit path argument) is unaffected - it still
    dispatches straight to the matching CLI subcommand regardless of cwd,
    exactly as before.
  - New `unren.ui.interactive.launch()` (called from `unren.cli.main()`
    instead of `run()` directly) implements this cwd pre-check; `run()`
    itself is unchanged and still used directly by every existing
    unit/integration test that drives the menu loop.
  - New locale key `menu.no_game_in_cwd` in both `en.json`/`de.json`.
- Tests: 5 new unit tests (`tests/unit/test_interactive_menu.py`) covering
  `launch()`'s three cases directly (in-game cwd, non-game cwd, partial
  structure, default-cwd resolution, no-prompt-before-bailing regression
  guard) plus 4 new/updated integration tests
  (`tests/integration/test_cli.py`) exercising the real subprocess CLI in
  both cwd scenarios and confirming `unren <path>` behavior is unchanged
  regardless of cwd. Pre-existing bare-invocation/menu integration tests
  were updated to run with `cwd` set to a recognized game fixture, since
  bare `unren` no longer unconditionally opens the menu. Full suite:
  313/313 passed (`PYTHONPATH=src python3 -m pytest tests/ -q`).
