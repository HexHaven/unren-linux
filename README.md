# unren (UnRen-forall-linux)

A native Linux port of [`Lurmel/UnRen-forall`](https://github.com/Lurmel/UnRen-forall) — a
toolkit for inspecting and modifying [Ren'Py](https://www.renpy.org/) visual novel games
(RPA archive extraction, RPYC decompilation, console/debug/skip toggles, and more).

Upstream `UnRen-forall` is a Windows batch-script toolkit. This project reimplements its
functionality as a proper, testable, native Python CLI for Linux — no Wine, no `.bat`
execution, no Windows-only mechanisms (registry context menus, UAC elevation, CAB
extraction, PowerShell). See `docs/UPSTREAM-BEHAVIOR.md` for a full parity matrix comparing
upstream behavior to this port's design, and `Proposed-Bauplan.md` for the overall project
plan.

## Credit & License

This project is a derivative work of `Lurmel/UnRen-forall`, licensed under the
**GNU General Public License v3.0 or later (GPLv3+)**. All credit for the original toolkit
design, detection algorithms, and vendored-tool integration (rpatool, unrpyc, etc.) goes to
its original author(s). See [`LICENSE`](./LICENSE) for the full license text.

This is an independent, unofficial port — not affiliated with or endorsed by the upstream
project maintainers.

## Status: Milestone 3 — RPYC Decompilation

Detection/diagnostics (Milestone 1), RPA archive **extraction** (Milestone 2), and RPYC
**decompilation** (Milestone 3) are implemented. Game-patching actions (console/debug/skip
toggles etc.) are not yet available — those land in later milestones (M4+).

Currently available:

- `unren detect [PATH]` — detect whether `PATH` (default: cwd) is a Ren'Py game, and report
  its Ren'Py generation/version, resolved Python runtime, and any archives found.
- `unren doctor [PATH]` — environment/tooling diagnostics: OS info, game detection result,
  Python runtime, archive formats present, and availability of external tools (`7z`,
  `p7zip`, `git`).
- `unren extract [PATH]` — extract RPA archives (v1/.rpi, v2, v3, v3.2) found under `PATH`.
  Defaults to a separate `unren-extracted/` folder next to the game root (never touches the
  original `.rpa` files or the `game/` tree unless `--in-place` is explicitly given).
  `--output PATH` extracts into an arbitrary destination instead. `--dry-run` (global flag)
  computes and prints the full plan without writing anything. Existing destination files are
  never silently overwritten — re-run with `--force` to overwrite (existing files are backed
  up first under `<game_root>/.unren/backups/`). Formats not yet supported for extraction
  (RPAN-3.0/ZiX-12A/12B/SVAC-1.0/RWA-3.0 "neutron" archives) are reported per-archive rather
  than guessed at.
- `unren decompile [PATH]` — decompile `.rpyc`/`.rpymc` files found under `PATH` to `.rpy`
  using a version-pinned, vendored copy of
  [`CensoredUsername/unrpyc`](https://github.com/CensoredUsername/unrpyc) (see
  `src/unren/vendor/README.md` for full provenance). Automatically selects the correct
  variant + Python runtime for the detected Ren'Py generation: the "current" variant
  (v2.0.3, Python 3.9+) for Ren'Py >=8, the "legacy" variant (v1.3.2, real Python 2) for
  Ren'Py <=7 when a Python 2 runtime is resolvable (system or Ren'Py-bundled), falling back
  to the "current" variant otherwise (documented risk: Python 2 is frequently unavailable on
  modern systems — the fallback was verified to still successfully decompile real Ren'Py
  7-era files). A `.rpyc`/`.rpymc` file whose container header matches neither known RPYC
  format is reported as a per-file error, never silently skipped. Same output-management
  (`unren-decompiled/` default, `--output`, `--in-place`) and overwrite-protection
  (`--force` + `.unren/backups/`) contract as `extract`. `--try-harder` passes through to
  unrpyc's own obfuscation-workaround flag.
- All commands support `--json` for machine-readable output.

`console`, `devmode`, `all` subcommands are registered in the CLI but are stubs that print
"not yet implemented" and exit non-zero — they are listed so `unren --help` documents the
intended full surface, but do nothing destructive.

Detection is **read-only** and **fail-closed**: if the Ren'Py generation/version cannot be
positively established via any of the seven detection strategies, it is reported as
`unknown` rather than guessed — and `decompile` in turn refuses to pick a decompiler variant
for an `unknown` generation rather than guess.

## Install

Requires Python >= 3.10.

### From source, with [uv](https://github.com/astral-sh/uv) (recommended for development)

```bash
git clone <this-repo> unren-forall-linux
cd unren-forall-linux
uv venv --python 3.11 .venv
uv pip install -e '.[dev,ui,paths]'
```

### As a tool, with `uv tool` or `pipx`

```bash
uv tool install /path/to/unren-forall-linux
# or
pipx install /path/to/unren-forall-linux
```

Optional extras:

- `ui` — installs [`rich`](https://pypi.org/project/rich/) for nicer console output
  (falls back to plain text if not installed).
- `paths` — installs [`platformdirs`](https://pypi.org/project/platformdirs/) for
  standard config/cache directory resolution.
- `dev` — installs `pytest`/`pytest-cov` for running the test suite.

## Quickstart

```bash
# Detect a Ren'Py game
unren detect /path/to/game

# Detect the game in the current directory
unren detect

# Environment + tooling diagnostics
unren doctor

# JSON output, e.g. for scripting
unren doctor --json
unren detect /path/to/game --json

# Version
unren --version
```

Example `unren detect` output against a Ren'Py 8-style fixture:

```
Root:            /path/to/renpy8_game
Game found:      yes
game/ dir:       /path/to/renpy8_game/game
renpy/ dir:      /path/to/renpy8_game/renpy
Ren'Py version:  current (major 8)
Python runtime:  /usr/bin/python3 (3.11.x, source=system)
Archives found:  1
  - game.rpa  [RPAN-3.0]
```

## Development

```bash
uv pip install -e '.[dev,ui,paths]'
pytest tests/ -v
```

Test fixtures for the Ren'Py detection cascade live under `tests/fixtures/` — synthetic,
minimal game directory trees for Ren'Py 6, 7, and 8 style layouts, used by both unit tests
(exercising individual detection strategies) and integration tests (exercising the CLI
end-to-end).

## Roadmap

See `Proposed-Bauplan.md` for the full milestone plan. Upcoming milestones add RPA
extraction, RPYC decompilation, and the various game-patching actions (console/debug mode,
skip toggles, quicksave, rollback, etc.) documented in `docs/UPSTREAM-BEHAVIOR.md`.
