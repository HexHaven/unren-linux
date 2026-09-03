unren (UnRen-forall-linux) 0.1.0 — Release Candidate
======================================================

Native Linux port of `Lurmel/UnRen-forall` (GPLv3), a Ren'Py game
detection/unlocking/utility toolkit. Original upstream is a Windows-only
batch-script toolkit; this project reimplements the same feature set as a
proper, testable, cross-platform-capable Python CLI, targeting Linux first.

Supported platform for this release
------------------------------------

**Arch Linux / CachyOS only.** Debian/Ubuntu/Fedora packaging and testing
were explicitly descoped by operator directive during Milestone 6/7 and are
not part of this release. The codebase itself has no Arch-specific runtime
dependency (pure Python 3.10+, only `rich`/`platformdirs` as optional
extras) — a Debian/Ubuntu/Fedora package is a plausible future milestone,
just not validated for this release.

Install
-------

    # From a repo checkout, via pipx (recommended, any distro incl. Arch):
    pipx install /path/to/UnRen-forall-linux

    # Or via uv:
    uv tool install /path/to/UnRen-forall-linux

    # Arch/CachyOS native package:
    cd packaging/arch && makepkg -si

`unren --version` / `unren doctor` both work correctly from any directory
after install, with zero repo-checkout dependency at runtime.

What's supported (feature summary)
-----------------------------------

  - `unren detect [PATH]` / `unren doctor [PATH]` — Ren'Py game detection
    (7-step fail-closed cascade covering generations 6/7/8) and environment
    diagnostics (OS, Python runtime, archive formats present, external
    tool availability).
  - `unren extract [PATH]` — RPA archive extraction (RPA-1.0/2.0/3.0/3.2),
    from-scratch reimplementation, no external `rpatool` dependency.
    `--output`, `--in-place`, `--force` (with automatic backup), `--dry-run`.
  - `unren decompile [PATH]` — RPYC decompilation for Ren'Py 6/7/8, using a
    vendored, version-pinned `unrpyc` (v2.0.3, Python 3.9+) that alone
    covers all three generations (see "Python 2 legacy" below).
  - `unren console enable` / `devmode enable` / `skip enable` /
    `skipall enable` / `rollback enable` / `quicksave enable` /
    `quickmenu enable` / `nosync enable` — idempotent, additive `.rpy`
    game-config patches, 1:1 behavioral parity with upstream's equivalent
    toggles.
  - `unren cleanup restore` / `cleanup delete` — restore or permanently
    delete `.unren/backups/` entries created by `--force` operations.
    `delete` requires `--yes` (irreversible).
  - `unren all [PATH]` — runs every non-destructive action above in a safe,
    fixed order in one invocation.
  - Bare `unren` (no subcommand) launches an interactive menu wrapping the
    same CLI commands — structural parity between menu and CLI, no
    divergent logic paths.
  - `--json` on every command for machine-readable output; `--language`
    (German/English, more via `locales/*.json`) and `--no-color` for
    human-readable output.

Every command supports `--dry-run` (computes and reports the full plan
without writing/creating anything) and reports errors deterministically —
see "Error handling" below.

Ren'Py generation coverage
----------------------------

Ren'Py 6, 7, and 8 are all supported for detection, extraction, and
decompilation. Decompilation coverage was independently verified against
77 real, upstream-sourced `.rpyc` files spanning all three generations
(official Ren'Py 6.18.3 SDK output plus upstream `unrpyc`'s own certified
7.7/8.2 test corpora) with zero failures and byte-identical output where a
reference existed — see `docs/UNRPYC-COVERAGE.md` for the full methodology
and results.

Python 2 legacy path
----------------------

A vendored, real-Python-2 `unrpyc` (v1.3.2) ships alongside the primary
Python-3 decompiler for provenance/parity reasons (see
`docs/UNRPYC-COVERAGE.md`), but is **not required** for correct Ren'Py 6/7/8
decompilation — the primary Python-3 decompiler alone handles all three
generations correctly. The Python-2 path remains available as a documented
fallback for the one known gap (genuine, untouched Screen Language 1
source, which the modern decompiler cannot parse at all) and was
confirmed still functional via a real Python 2.7.18 interpreter during
Milestone 3.5's verification pass. No Python 2 interpreter is required for
normal use of this tool.

Error handling / determinism
-------------------------------

Every command follows the same contract: on success, exit 0 with a report
(text or `--json`); on failure, exit 1 (or 2 for CLI usage errors) with a
translated, human-readable message and a matching structured `--json` error
shape (`{"ok": false, "error": {"code", "message", "details"}}`) — never a
raw stack trace. This release fixes the one remaining gap found during
Release Candidate testing: filesystem-level failures (e.g. attempting to
write into a read-only `game/` directory or a read-only mount) previously
escaped as an unhandled Python traceback instead of a structured error; they
are now caught and reported the same way as every other error (new
`filesystem-error` error code). Unknown/undetectable Ren'Py generations,
corrupt or unrecognized RPA/RPYC containers, and missing Python runtimes
were already handled deterministically (fail-closed with a clear reason,
never a silent guess) and remain unchanged.

`--dry-run` is verified reliable: it never writes to or creates anything on
disk under any tested condition, including a read-only target filesystem
(confirmed via a byte-for-byte before/after directory-listing diff).

Testing
-------

  - 304 automated tests (`.venv/bin/python -m pytest tests/`), all passing:
    unit tests for every detection/adapter/action module plus end-to-end CLI
    integration tests (subprocess against the real installed entry point).
  - 7 new Release Candidate edge-case tests added this milestone
    (read-only-filesystem determinism, nonexistent-path handling, unknown
    Ren'Py generation handling) — see
    `tests/integration/test_release_candidate_edge_cases.py`.
  - CI (`.github/workflows/ci.yml`): a `pytest` matrix job and a full
    `makepkg` build/check/package job, both against a real Arch userland
    (the official `archlinux:base-devel` container image). Independently
    reproduced locally in a fresh Docker container as part of this
    milestone: full test suite green, `makepkg -s` build/check/package
    succeeded end-to-end as an unprivileged user, and the resulting package
    installed via `pacman -U` and ran correctly (`unren --version`/`unren
    doctor` from `/tmp`) — a fuller reproduction than Milestone 6 achieved,
    since that sandbox lacked interactive `sudo`.
  - Performance: a synthetic 1000-member/~4 MB RPA archive extracted via the
    full CLI path in ~0.15s wall-clock — no scaling concern for realistic
    game archive sizes.

Known limitations
--------------------

  - Debian/Ubuntu/Fedora: not packaged or tested for this release (Arch/
    CachyOS-only scope, operator directive).
  - Addon installers (Universal Gallery Unlocker, Universal Choice
    Descriptor, Universal Transparent Text Box, 0x52_URM, custom addon
    installer), `replace_anyname`, `extract_text`, the `altrpatool`/"with
    key" extraction fallback, and WOS SHIELD pre-decrypt remain out of
    scope (SHOULD/COULD priority items, not MUST — see
    `docs/UPSTREAM-BEHAVIOR.md` §5).
  - AUR submission / package signing not yet done — PKGBUILD is provided
    for local `makepkg` builds from a repo checkout.
  - No context-menu registry integration or self-update (explicit
    non-goals on Linux — see `docs/UPSTREAM-BEHAVIOR.md` §3).

Full milestone-by-milestone history: see `CHANGELOG.md`.
