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
