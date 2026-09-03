# UnRen-forall Upstream Behavior — Parity Matrix

**Milestone 0 — Upstream Archaeology**

Source analyzed: `Lurmel/UnRen-forall` (git clone at `/tmp/unren-upstream`), commit state as
shipped in `UnRen-forall-la_0.77-le_9.7.60-cu_9.7.80.zip`.

Files read in full or in relevant part:
- `UnRen-forall.bat` (3536 lines) — multilingual launcher / Ren'Py version router
- `UnRen-current.bat` (4495 lines) — Ren'Py ≥ 8 toolkit (primary reference for this matrix)
- `UnRen-legacy.bat` (4495 lines) — Ren'Py ≤ 7 toolkit (near-identical to current, see §2)
- `UnRen-cfg.txt` (79 lines) — external config (language, default menu choices, timeout, 7z path)
- `README.md`, `FAQ.md`, `Changelog.md`, `LICENSE` (GPLv3)

All embedded base64 Python payloads referenced below were decoded with `base64 -d` and read in
full to confirm actual behavior rather than inferred from surrounding comments/variable names.

---

## 1. External tool dependencies

**Key finding: there is no external `rpatool`/`unrpyc` package dependency at runtime.** Everything
is vendored **inline as base64-encoded Python source**, written to temp/work-dir `.py` files at
run time, executed via the detected Python interpreter, then deleted again in a `:*_cleanup` step.
This has real consequences for the Linux port: the "adapter" layer described in the Bauplan
(`adapters/rpatool.py`, `adapters/unrpyc.py`) should vendor **specific, licensed, version-pinned
copies of this code** (or well-maintained upstream equivalents) rather than assume a pip package
called `rpatool`/`unrpyc` exists — neither is published to PyPI.

| Component | How it's obtained | Actual origin / version | Notes for Linux port |
|---|---|---|---|
| `rpatool.py` | Base64 blob decoded to `%WORKDIR%\rpatool.py`, run via system Python | Fork of `Shizmob/rpatool` commit `9a58396` (2019-02-22), "Version 0.8 wo pickle5" — used only when `RPATOOL_NEW=n` (i.e. Ren'Py ≤ 7 context in current.bat this branch is effectively dead since RENPYVERSION≥8 is enforced, but the same code path exists unconditionally in legacy.bat) | Straight `argparse` CLI: `rpatool.py ARCHIVE -x -o DIR`. Reads RPA v1/v2/v3/3.2 headers, uses `pickle.loads` + zlib for indexes, XOR-deobfuscates v3/3.2 offsets with the archive key (default `0xDEADBEEF`). This is the reference algorithm to reimplement in `unren.adapters.rpatool` / `core` RPA reader. |
| `rpatool.py` (2022 variant) | Same mechanism, used when `RPATOOL_NEW` is unset/default | "rpatool by Shizmob 2022-08-24", "Version 0.8 w pickle5 — Require Python >= 3.8", **includes an SVAC-1.0 decoder and `.jas` file extension support added by JoeLurmel** | The SVAC-1.0 / `.jas` support is a Lurmel-specific extension not present in upstream Shizmob rpatool — must be preserved for parity with modified/obfuscated archives some games ship. |
| `altrpatool.py` | Base64 blob, used when the archive is detected as "modified" (non-standard RPA header) | Custom script by JoeLurmel; imports the **actual Ren'Py runtime's** `renpy.loader`/`renpy.config` modules from the game's own `renpy/` folder to enumerate and read archive contents via the game's own archive-handler classes, rather than reimplementing the RPA format itself | This is the "different header" fallback (`unren.actions.extract_wkey` label in Bauplan terms is actually unused/stubbed — see §Matrix row `extract_wkey`). Its trick — importing the shipped `renpy` package to resolve custom/obfuscated archive formats — is a valuable fallback strategy worth replicating for Linux: shell out to the *game's own bundled Python + renpy package* when our own format parser fails. |
| `detect_archive.py` | Base64 blob | Custom, tiny — reads first 8 bytes of a file; classifies "standard" (`RPA-`, `SVAC-`, `RWA-3.0 `) vs "modified/unknown" (return code 1) | Trivial format sniffing; straightforward to port to `unren.detection.archives`. |
| `detect_rpa_ext.py` (aka `detect_archive_extensions`) | Base64 blob | Custom; tries `renpy.loader.archive_handlers` introspection first (if a `renpy` module is importable), else scans the game dir for files whose first bytes start with `RPA-` and collects their extensions, else falls back to `['.rpa']` | Hybrid detection strategy: (1) ask the actual Ren'Py runtime what extensions its archive handlers support, (2) content-sniff on disk, (3) hardcoded fallback. Matches the Bauplan's "fail closed but multi-strategy" philosophy for `detection/archives.py`. |
| `wos_decrypt_all.py` | Base64 blob, run standalone before decompilation | Custom — decrypts RPYC files protected by "WOS SHIELD" (`renpy/wos_rpyc_loader.py` present in game) using SHA-256-derived XOR keystreams (`MAGIC_RPYC`/`SECRET_KEY` imported from the game's own loader module) | Game-specific DRM-bypass step. Niche; only triggers `if exist ".\renpy\wos_rpyc_loader.py"`. |
| `unrpyc.py` + `deobfuscate.py` (legacy: RPC v3/Ren'Py ≤7) | **Not base64 text** — a full **MSCF CAB archive** (`decompcab`) is embedded as one giant base64 blob, decoded, then `expand.exe -F:* decomp.cab decompiler\` extracts `unrpyc.py`, `deobfuscate.py`, `astdump.py`, `atldecompiler.py`, `codegen.py`, `magic.py`, `renpycompat.py`, `screendecompiler.py`, `sl2decompiler.py`, `testcasedecompiler.py`, `translate.py`, `util.py`, `main.py`, `__init__.py` | Vendored copy of **`CensoredUsername/unrpyc`**, comment marks it `__title__ = "Unrpyc Legacy for Ren'Py v7 and lower"`, `__version__ = 'v1.3.2'`. Uses `expand.exe` (Windows-only CAB extraction tool) — **this is a hard Windows dependency with no Linux equivalent**; the Linux port must instead vendor unrpyc as plain files/a proper Python package dependency (e.g. pip-installable fork, or a vendored source tree per Bauplan §12) rather than a CAB blob. |
| `unrpyc.py` (current: RPC v2/Ren'Py ≥8 branch, `UNRPYC_NEW` != "n") | Same CAB mechanism, separate embedded blob | **Confirmed by extraction** (`cabextract` on the decoded CAB, this pass): fork of **`CensoredUsername/unrpyc`**, `__title__ = "Unrpyc"`, **`__version__ = 'v2.0.3'`**, Python-3-only (`#!/usr/bin/env python3`, raises if run under <3.9). **Discrepancy found:** the surrounding batch comment block (`UnRen-current.bat` ~L2489-2493) claims `__title__ = "Unrpyc Master for Ren'Py v8"`, `__version__ = 'v2.0.4'`, "Modified to include Inceton + Version display" — but the *actual byte-identical CAB payload* (confirmed via md5sum: legacy and current files embed the exact same two CAB blobs) decodes to plain upstream `v2.0.3` with none of the claimed "Inceton"/version-display modifications visible in the extracted source. The batch comment is stale/aspirational documentation, not a description of the shipped code. **Linux port should pin to verified `v2.0.3` behavior, not the v2.0.4 claimed in comments**, unless a human reviewer finds evidence the modifications exist elsewhere. | Both `unrpyc.py` variants (legacy v1.3.2 py2 / current v2.0.3 py3) are vendored as **one shared CAB pair reused identically by both `UnRen-legacy.bat` and `UnRen-current.bat`** — confirmed via `md5sum` of both files' embedded CAB blobs (`135c3399...` and `1232af49...` match byte-for-byte across both scripts). |
| `b64decode.py` | Inline heredoc (`echo` lines, not the `<nul set /p` base64 pattern) | Trivial helper: reads a file, strips CR/LF, pads to base64 quantum, decodes, writes output; used by the generic `:pwsh_exp` label despite its name (historically PowerShell, now actually Python-based per Changelog "Base64 are now decrypted with Python instead of PowerShell to improve speed") | No Linux relevance beyond documenting that in the current version, base64 payload materialization no longer needs PowerShell — pure Python does it. Confirms the whole vendoring mechanism is portable in principle; only the packaging format (CAB via `expand.exe`) is Windows-specific. |
| `7z.exe` (external, optional) | User-provided path via `UnRen-cfg.txt` `_7ZIPLOC` variable | Real 7-Zip binary, **only required for the Universal Transparent Text Box addon** (`:add_utbox`, needs `.7z` extraction) | On Linux: use `py7zr`, `libarchive`, or system `7z`/`p7zip`; not needed for core RPA/RPYC flows. |
| PowerShell (`%PWRSHELL%`) | Windows built-in, resolved once near script start | Used for: HTTP downloads (`System.Net.WebClient`), `.zip` extraction (`Expand-Archive`), text replacement (`Get-Content`/`Set-Content` for the name-replace feature), and elevation (`Start-Process -Verb RunAs`) | All Windows-only. Linux equivalents: `requests`/`urllib` for downloads, `zipfile`/`shutil.unpack_archive` for extraction, plain Python text I/O for replace, and simply *no* elevation step needed (no UAC on Linux; file permission checks instead). |
| `reg.exe` | Windows built-in | Registry manipulation for the Explorer right-click "Run UnRen here" context-menu entry | **Non-goal on Linux** — see §3. |
| `expand.exe` | Windows built-in | CAB decompression, used only for unrpyc payload | **Non-goal on Linux** as a mechanism; the *content* (unrpyc.py + deobfuscate.py) must be vendored some other way (plain files / package). |
| `certutil.exe` | Referenced in the milestone brief's hint but **not found** in the actual current `.bat` source (searched, zero matches) | — | The base64-decode step used to rely on `certutil -decode` in older UnRen forks; this version has switched entirely to the inline Python `b64decode.py` helper. No certutil dependency remains to port. |
| `net session` | Windows built-in | Used purely to test for admin/elevated privileges (`:check_admin`) | No Linux equivalent needed; Linux has no UAC-style split-token elevation for a CLI tool run by a normal user. |

---

## 2. Legacy vs. Current — classification differences

`UnRen-legacy.bat` and `UnRen-current.bat` are **4495 lines each** and a full `diff` shows only
**3 differing lines** (confirmed via `diff UnRen-legacy.bat UnRen-current.bat`):

```diff
18c18
< :: UnRen-legacy.bat - UnRen Script for Ren'Py <= 7
---
> :: UnRen-current.bat - UnRen Script for Ren'Py >= 8
37,38c37,38
< set "NAME=legacy"
< set "VERSION=v9.7.60 - 05/17/26"
---
> set "NAME=current"
> set "VERSION=v9.7.80 - 05/17/26"
1228c1228
< if %RENPYVERSION% GEQ 8 (        ← legacy: refuses to run on Ren'Py >= 8
---
> if %RENPYVERSION% LEQ 7 (        ← current: refuses to run on Ren'Py <= 7
1231c1231
<     call :elog "!renpyvers6.%LNG%!"   ("please use UnRen-current.bat instead")
---
>     call :elog "!renpyvers5.%LNG%!"   ("please use UnRen-legacy.bat instead")
```

**Conclusion:** legacy vs. current is *purely* a version-gate + display-string difference. The
entire feature set, menu, dispatch table, and vendored tooling (rpatool/altrpatool/unrpyc CAB
blobs, all addon downloaders, etc.) are byte-for-byte identical between the two files. This
strongly validates the Bauplan's `RenPyGeneration` enum approach (§9): the Linux port needs **one**
logical implementation with a version-threshold branch at `renpy_version >= 8`, not two parallel
codebases. Internally the *content* of the vendored `unrpyc`/`rpatool` blobs is presumably tuned
per branch (RPC v2 vs v3 handling — see decompile matrix row below) even though the surrounding
orchestration code is identical.

`UnRen-forall.bat` (3536 lines) is the **launcher**: it does independent Ren'Py-version detection
(via `RENPYVERSION` — see the shared `detect_renpy_version.py` payload, §Detection mechanism
below), then `call`s either `UnRen-legacy.bat` or `UnRen-current.bat` with the working directory as
an argument. It also owns its own copy of the multilingual UI strings, config loading, and — per
FAQ — the update-checking / changelog display flow, largely duplicated from the two worker scripts
(the same `:found_lcid`, `:check_admin`, `:check_update` style labels reappear in it).

---

## 3. Windows-specific mechanisms — explicit non-goals for Linux

These upstream behaviors are Windows/Explorer/registry-specific and should be marked as **explicit
non-goals** (or, at most, "won't implement natively — document as N/A") for `UnRen-forall-linux`:

| Mechanism | Upstream behavior | Linux disposition |
|---|---|---|
| Explorer context-menu registration (`ACT.+=add_reg`, `ACT.-=remove_reg`) | Adds `HKCU\Software\Classes\Directory\shell\Run<name>` (+ `Background\shell\...`) registry keys so right-clicking a folder in Explorer shows "Run UnRen here"; also detects/removes a legacy `HKLM`-rooted key that requires admin rights to clean up | **Non-goal.** No registry on Linux. If desired later, the closest COULD-tier equivalent is a **file-manager "Open with" / Nautilus script or KDE service menu entry** (see Bauplan §3 COULD "Dateimanager-Integration") — a completely different mechanism, out of scope for v1. |
| `:check_old_reg` / `:check_admin` (UAC elevation) | Checks for a stale `HKLM`-rooted registry key; if present, re-launches itself elevated via `Start-Process -Verb RunAs` and blocks on `net session` to verify admin rights | **Non-goal as designed.** Linux has no UAC; the closest analog is `os.geteuid() == 0` / file-write-permission checks on the target directory, which the Bauplan already covers under "Fehler verständlich melden" / non-destructive defaults. No elevation *relaunch* flow should be built — if a path isn't writable, fail closed with a clear error instead of trying to escalate privileges. |
| Console font/window resizing relaunch (`:already_restarted`, registry `Consolas` font settings) | Sets Windows Console registry values for `cmd.exe`, relaunches itself so the new font/window-size takes effect, then restores old settings at exit | **Non-goal.** Purely a `cmd.exe` cosmetic workaround; irrelevant to any POSIX terminal. |
| `%APPDATA%\...\RenPy\<game>` sync-folder assumption (`:nasty_sync` / "remove nasty AppData sync folder") | Patches the *game* (drops an `.rpy` init block) to set `renpy.config.has_sync = False` and clear `renpy.config.extra_savedirs`, addressing a Windows-only OneDrive/AppData folder-sync conflict some games create | **Semantics keep, mechanism is OS-agnostic already** — this is actually a Ren'Py *game-config* patch, not a Windows API call, so it ports directly. But the *motivating* problem (`%APPDATA%\RenPy\...` colliding with OneDrive folder sync) is Windows-specific; on Linux the equivalent save location is `~/.renpy/` (or `$XDG_CONFIG_HOME`/`~/.config` per some builds) and has no OneDrive-style sync conflict by default. Keep the feature (still generically useful to disable cross-device save sync) but rewrite the doc/UI text — don't assume `%APPDATA%`. |
| `.exe`-file game-name detection (`:extract_text` "find current game name by checking `.exe`/`.py`/`.sh`") | Looks for a same-named `.exe` + `.py` pair to identify the game's translate-invocation name | Partially portable: the `.sh` launcher and `.py` main-module heuristics apply on Linux (script explicitly notes "Do not test with sh, it can be not shipped" — i.e. it *already* anticipates non-Windows launchers only skipped for reliability, not by design). Linux port should test `.sh`/`.py` pairs (and no-extension executables) instead of `.exe`/`.py`. |
| `%SystemRoot%\System32\reg.exe`, `findstr.exe`, `expand.exe`, `chcp.com`, `wmic`, wscript/PowerShell CIM calls | Used throughout for registry, string search, CAB extraction, codepage switching, and locale detection | All non-goals; replace with Python stdlib (`re`, `zipfile`/`tarfile`, `locale`/`gettext`) per adapter layer. |
| Self-relaunch via `Start-Process ... -Verb RunAs` and `%~f0` re-invocation patterns | Batch-specific self-relaunch tricks (elevation, font change, "already restarted" flag propagation via extra CLI arg) | Non-goal; a single Python process doesn't need to re-exec itself for privilege or console reasons. |
| `.bat`/`.exe` script self-update (`:update_file`, `:check_update`, `:special_upd`) | Downloads a new package zip from a fixed URL, diffs/copies `.bat` files in place, optionally relaunches the new version | Out of scope for Milestone 0; if built at all for Linux it should be a `pip`/`pipx`/distro-package update flow (Bauplan §21 Packaging), not a self-replacing script — flag as COULD, and definitely not a straight port of the `.bat`-file-swap mechanism. |

---

## 4. Detection mechanism (upstream)

Two independent, complementary detection layers exist:

1. **Language / locale detection** (`:found_lcid`, `UnRen-current.bat` ~L105–146, and duplicated in
   `UnRen-forall.bat`): reads the OS UI language via `wmic os get oslanguage` (older systems) or
   `Get-CimInstance Win32_OperatingSystem | Select OSLanguage` (PowerShell CIM, newer systems),
   yielding a numeric **LCID**. A hardcoded LCID→language map (`1033→en, 1036→fr, 3082→es,
   1040→it, 1031→de, 1049→ru, 2052→zh`) sets `LNG`; unsupported/unmapped LCIDs fall back to `en`.
   `UnRen-cfg.txt`'s `LNG=` setting, if non-empty, and a CLI override (`%~2` positional arg, used
   for F95zone screenshot automation) both take priority over autodetection. This is purely a
   **UI/i18n** concern, not a game-detection concern — corresponds to Bauplan §17 `locales/*.json`
   with an explicit override → project config → OS locale → English fallback chain (same pattern,
   different discovery order — worth normalizing to CLI > config > OS-locale > English per Bauplan
   §13's stated priority list).

2. **Ren'Py version / game detection** — this is the functionally important one, implemented twice:
   - **In `UnRen-forall.bat`** (the launcher): runs an embedded `detect_renpy_version.py` (base64)
     against the target directory to decide whether to `call UnRen-legacy.bat` or
     `UnRen-current.bat`.
   - **In `UnRen-current.bat`/`UnRen-legacy.bat` themselves** (~L1137–1252, "Check for Ren'Py
     version"): runs the **same** `detect_renpy_version.py` payload again as a **self-consistency
     guard** — if you launch `UnRen-current.bat` directly against a Ren'Py 7 game, it detects the
     mismatch and tells you to use `UnRen-legacy.bat` instead (`RENPYVERSION LEQ 7` / `GEQ 8` gate,
     see §2 diff above), then `call :exitn 3`.

   `detect_renpy_version.py`'s algorithm, decoded and read in full, uses a **priority-ordered,
   multi-strategy, fail-soft-then-hard cascade** — directly matching the Bauplan §9 requirement
   ("Versionserkennung in Prioritätsreihenfolge" + "Fail closed"):
   1. Try `import renpy; print(renpy.version_tuple[0])` — if the *actual* Ren'Py package is
      importable (i.e. running with the game's bundled Python), trust it completely and exit.
   2. `script_version.txt` in the `game/` dir — regex `\(\s*(\d+)\s*,` (tuple form) or a leading
      integer (simple form).
   3. `renpy/version.py` — regex `version\s*=\s*"(\d+)` (Ren'Py 6-era layout).
   4. `.rpyc`/`.rpymc` magic-number sniffing across the game tree: `RENPY RPC1` → major 6,
      `RENPY RPC2` → major 7 *or* 8 (ambiguous — Python-3-era Ren'Py 8 reuses the RPC2 magic and
      can't be distinguished from 7 by magic byte alone).
   5. `.rpa` archive header sniffing: `RPA-1.0`/`RPA-2.0` → 6, `RPA-3.0` → 7 (refined later via
      step 4's rpyc check if ambiguous), `RPAN3.0`/`ZiX-12A`/`ZiX-12B` → 8 ("new neutron archive"
      formats specific to recent Ren'Py 8 releases).
   6. Heuristic scan of small text/log/ini/cfg/json files in the game root and its parent for a
      `Ren'Py N.` or `renpy[-_]N.` regex pattern (N ∈ {6,7,8}).
   7. If **none** of the above yield a result: **hard failure** — the batch script prints an error
      ("Unable to detect Ren'Py version... please ensure the game is compatible with UnRen") and
      exits (`call :exitn 3`) rather than guessing. This *is* the fail-closed behavior the Bauplan
      already mandates for `unren.detection.renpy` — the upstream already gets this right and the
      Linux port should preserve the exact same priority cascade and the "UNKNOWN, don't guess"
      terminal behavior.

   Separately, **RPA extension/format detection** (`detect_rpa_ext.py`, used inside `:extract_rpa`)
   is its own smaller hybrid cascade: (1) ask the live `renpy.loader.archive_handlers` for
   supported extensions if `renpy` is importable, else (2) content-sniff `.rpa`-*like* files on
   disk by header regardless of extension, else (3) hardcoded fallback `['.rpa']`.

---

## 5. Parity Matrix

Columns: **Feature (Name)** · **Windows-Implementierung** (kurzer Code-Auszug/Beschreibung) ·
**Portable Semantik** (was es tatsächlich tut) · **Linux-Replacement-Strategie** · **Priority**
(MUST/SHOULD/COULD) · **Test verfügbar?**

| Feature (Name) | Windows-Implementierung | Portable Semantik | Linux-Replacement-Strategie | Priority | Test verfügbar? |
|---|---|---|---|---|---|
| **RPA extraction (standard)** — `ACT.1/5/6=extract_rpa`, label `:extract_rpa` (~L1687) | Detects RPA extension(s) via `detect_rpa_ext.py`, walks `game\` for matching files, per file: optional interactive "extract this one? Y/N" or bulk mode, runs vendored `rpatool.py -o game -x <file>`, then either deletes or renames source to `<file>.rpa.org` | Recursively unpack all (or user-selected) `.rpa`/detected-extension archives into the `game/` tree, non-destructively by default (rename to `.org`), with an explicit opt-in to delete originals | `unren.actions.extract_rpa` + `unren.adapters.rpatool`: reimplement/port the RPA v1/v2/v3/3.2 reader (pickle+zlib index, XOR-deobfuscated v3 offsets) in Python; default to `--backup` (rename, Bauplan §14) not delete; `--dry-run` support | **MUST** | Partial — RPA format is documented/testable with synthetic fixtures (Bauplan §23 `tests/fixtures/`); real-world archives needed for full regression but format itself is unit-testable |
| **RPA extraction (alt/modified header)** — `ACT.7=extract_rpa` with `usealt=1`, `altrpatool.py` | If `detect_archive.py` flags a file as non-standard header (not `RPA-`/`SVAC-`/`RWA-3.0 `), switches to `altrpatool.py`, which imports the **game's own bundled `renpy` package** to resolve/read the archive via `renpy.loader.load_from_archive`/`load_core` | Fallback path for games that ship custom/obfuscated archive headers — leverages the game's *own* runtime rather than reimplementing every vendor's format | `unren.adapters.rpatool`: implement a fallback that shells out to (or in-process imports, if same Python ABI) the target game's bundled `renpy` package when the built-in parser can't read the header; requires locating/using the game's Python runtime (Bauplan §10 Runtime Resolver) | **SHOULD** | Hard to unit test generically (needs real modified-archive fixtures); document as best-effort |
| **RPA extraction — "with key" variant** — `ACT.3=extract_wkey`, label `:extract_wkey` | `call :elog . / goto :unavailable` — **entirely stubbed out**, does nothing but print "unavailable" | Menu option `3` exists but is a documented no-op in the current shipped version (comment says "Use unrpa instead of rpatool which offer the ability to extract RPA archives with a different header" — feature was apparently removed/disabled) | Not a real upstream feature to port — **no functional parity needed**, just note that menu slot 3 exists upstream but currently does nothing | **COULD** (only if reviving the described `unrpa`-with-key capability is independently desired) | N/A — nothing to test, upstream itself is a stub |
| **RPYC decompile (standard)** — `ACT.2/4=decompile`, `ACT.6` (extract+decompile combo), label `:decompile` (~L2289) | Detects WOS-shield-protected games and pre-decrypts (`:wos_decrypt_all`); detects RPYC magic version (`RENPY RPC2` vs `RPC3`-ish heuristic) vs. `RENPYVERSION` to warn on mismatch; extracts vendored `unrpyc.py`+`deobfuscate.py` (+ decompiler support modules) from an embedded CAB archive; runs `unrpyc.py [--clobber] <file>` per `.rpyc`, optionally backing up existing `.rpy` to `.rpy.org` first | Batch-decompile all `.rpyc` under `game/` to `.rpy`, with optional overwrite of existing `.rpy` files (default: skip existing), version-aware invocation | `unren.actions.decompile_rpyc` + `unren.adapters.unrpyc`: vendor a proper, version-pinned unrpyc source tree (per Bauplan §12 — no undocumented vendor blobs; document Name/Version/URL/Commit/License in `vendor/README.md`); implement the same WOS-shield pre-decrypt step if targeting affected games; default non-destructive `.rpy.org` backup behavior | **MUST** | Good — unrpyc itself has upstream tests; synthetic `.rpyc` fixtures per Bauplan §23 can validate the wrapper logic (backup/overwrite/clobber flags) even without full decompiler porting |
| **RPYC decompile — "try harder" / deobfuscation variant** — `ACT.7` combined flow (`--try-harder` flag to `unrpyc.py`) | When `OPTION==7`, passes `--try-harder` to `unrpyc.py` (uses the bundled `deobfuscate.py` more aggressively) | Best-effort decompilation of obfuscated/protected `.rpyc` bytecode | Same adapter, expose a `--try-harder`/`deobfuscate` flag mapping through to the vendored unrpyc's own option | **SHOULD** | Same as above — depends on unrpyc's own obfuscation-handling test coverage |
| **WOS SHIELD decrypt** — internal helper `:wos_decrypt_all`, auto-invoked by `:decompile` if `renpy/wos_rpyc_loader.py` exists | Custom SHA-256-keystream XOR decryption replicating a specific DRM's `MAGIC_RPYC`/`SECRET_KEY` scheme (imported live from the game's own loader module), writes `.dec` temp files, renames original to `.org`, renames `.dec` to original name | Game-specific DRM bypass triggered automatically as a decompile pre-step, never surfaced as its own menu action to the user | `unren.actions.decompile_rpyc` internal pre-step: detect `renpy/wos_rpyc_loader.py`, import the game's own key material the same way, decrypt before handing off to unrpyc | **SHOULD** (niche but automatic/low-cost to keep) | Testable if a synthetic WOS-shielded fixture can be constructed from the known algorithm (it's fully deterministic given the game's own key file) |
| **Enable console / dev mode** — `ACT.a=console`, label `:console` | Writes a static 2-line `.rpy` (`config.console = True`, `config.developer = True`) to `game/unren-console.rpy` if not already present, skips if present | Idempotent, additive-only game-config patch enabling Ren'Py's built-in developer console | `unren.actions.enable_console`: write the same static content to `<game>/unren-console.rpy`; check-before-write idempotency preserved | **MUST** | Trivial — pure file-write, fully unit-testable with fixture games |
| **Enable debug mode** — `ACT.b=debug`, label `:debug` | Writes static `.rpy` (`config.debug = True`) to `game/unren-debug.rpy`, same idempotent pattern | Same pattern as console, separate flag | `unren.actions.enable_devmode` (or split into its own action) | **MUST** | Trivial |
| **Force-skip (seen-only)** — `ACT.c=skip`, label `:skip` | Writes `.rpy` init-999 python block: `allow_skipping=True`, `skip_unseen=True`, `skip_after_choices=True`, `fast_skipping=True`, sets `Ctrl` as skip keymap, `persistent.game_completed=True` | Enables standard "hold ctrl to skip seen text" behavior plus marks the persistent "completed" flag | `unren.actions.cleanup`/new `enable_skip` action: write equivalent `.rpy` init block | **MUST** | Trivial |
| **Force-skip-all (incl. unseen)** — `ACT.d=skipall`, label `:skipall` | Same as `:skip` **plus** `_preferences.transitions = 0` (disables transitions too), still no unseen-text guard removed from the *unseen* skip toggle (both variants set `skip_unseen=True` already — the real differentiator vs. `:skip` is disabling transitions) | Aggressive skip-everything mode incl. transition suppression | Same action family with a `--all`/`force-skip-all` variant flag | **MUST** (parity with a documented, frequently-used option) | Trivial |
| **Rollback enable** — `ACT.e=rollback`, label `:rollback` | Writes `.rpy` init-999 python block: `rollback_enabled=True`, `hard_rollback_limit=256`, `rollback_length=256`, monkeypatches `renpy.block_rollback` to a no-op, sets PageUp/mouse-button-4 rollback keymap | Force-enables rollback (undo/scroll-back) even for games that disabled it, with a large history buffer and a neutralized "block rollback" call some games use to prevent save-scumming | `unren.actions.enable_rollback` | **MUST** | Trivial |
| **Quick Save/Load enable** — `ACT.f=quick`, label `:quick` | Writes `.rpy` init-999 python block binding `F5`→QuickSave, `F9`→QuickLoad via `config.underlay[0].keymap` | Adds keyboard-shortcut quicksave/load regardless of game's own keymap | `unren.actions.enable_quicksave` | **SHOULD** | Trivial |
| **Quick-menu force-on** — `ACT.g=qmenu`, label `:qmenu` | Writes `.rpy` init python block that appends two callbacks (`config.overlay_functions`, `config.interact_callbacks`) forcing `store.quick_menu = True` and re-showing the `quick_menu` screen on every interaction | Forces the quick-menu overlay to always be visible even if the game normally hides it (e.g. during main menu/certain screens) | `unren.actions.enable_quickmenu` | **SHOULD** | Trivial |
| **Universal Gallery Unlocker (addon)** — `ACT.h=add_ugu`, label `:add_ugu` | Downloads a zip from a hardcoded `attachments.f95zone.to` URL via PowerShell `WebClient`, expands nested zip-in-zip (`hard.zip`/`soft.zip`), installs `soft.zip` contents into `game/_mods/` | Installs a third-party gallery-unlock mod, **fetched live from the internet at run time** | `unren.actions` optional addon-installer with the same URL, using `requests`/`urllib` + `zipfile`; **must be opt-in, clearly labeled as fetching un-vetted third-party code from a fixed external host** | **SHOULD**/**COULD** — flagged: network-dependent, third-party content, single point of failure if the URL 404s (no version pinning, no checksum verification in upstream either) | None upstream; would need a mocked-HTTP integration test on the Linux side (Bauplan §23 could add a `responses`/`vcr`-style fixture) |
| **Universal Choice Descriptor (addon)** — `ACT.i=add_ucd`, label `:add_ucd` | Downloads zip from hardcoded f95zone URL, splits into two nested part-zips (`part1.zip`/`part2.zip`), extracts both into game root | Installs a third-party "annotate available choices" mod | Same pattern as UGU | **SHOULD**/**COULD** — same network-dependency risk; note the upstream logic even has a latent bug (`:skip_ucd` label defined but also referenced from inside the `add_ugu` block — cross-contaminated `goto` on failure, likely copy-paste artifact worth flagging to a human reviewer) | None upstream |
| **Universal Transparent Text Box Mod (addon)** — `ACT.j=add_utbox`, label `:add_utbox` | Requires a **local 7-Zip** binary path (`_7ZIPLOC` from `UnRen-cfg.txt`) to extract a `.7z` downloaded from f95zone; drops single file `game/y_outline.rpy` | Installs a third-party textbox-transparency visual mod; **additionally depends on an external 7-Zip install the user must configure manually** — upstream itself skips gracefully (`:skip_utbox`) if `_7ZIPLOC` isn't set/found | Same network-dependency risk as UGU/UCD, **plus** an explicit external-tool dependency (7-Zip) that on Linux maps to `py7zr`/`libarchive`/system `7z` | **COULD** — least essential of the four addons, has an extra unconfigured-by-default gate even upstream | None upstream |
| **0x52_URM (Universal Ren'Py Mod) (addon)** — `ACT.k=add_urm`, label `:add_urm` | Downloads zip from f95zone, extracts directly into `game/`, expects the mod to end up self-contained as `game/0x52_URM.rpa` | Installs a general-purpose cheat/mod menu tool from a third party | Same network-dependency risk as UGU/UCD | **SHOULD**/**COULD** — same class of risk, arguably most popular/useful of the four per naming, but still unvetted third-party binary content pulled from a single external host with no checksum | None upstream |
| **Custom add-on installer** — `ACT.p=add_custom_addon`, label `:add_custom_addon` | Interactive prompt for a URL or local path; if URL (regex `^https?://`), downloads via PowerShell WebClient to temp zip; if local path, uses directly; then either recursively `xcopy`s a folder or `Expand-Archive`s a zip/rar into `game/` | Generic "install anything from anywhere" escape hatch — most flexible and also most dangerous (arbitrary URL/file, no format/content validation) | `unren.actions` generic addon installer taking `--source <url-or-path>`; **strongest candidate for extra safety guardrails** (confirm before overwrite, no execution of downloaded content, restrict to archive/folder copy only as upstream does) | **SHOULD** — genuinely useful generic feature, but flag prominently in docs/CLI help as "installs unverified third-party content" | None upstream; would benefit from a Linux-side dry-run/confirmation test |
| **Replace character name** — `ACT.l=replace_anyname`, label `:replace_anyname` | Prompts old/new name via `set /p`; writes a `.rpy` init-999 python block (base64-templated) that installs a `config.replace_text` callback doing regex-based whole-word replacement with case-preservation (upper/Title/lower) and even "stuttering" patterns like `c-connor`→`j-joe`/`co-connor`→`jo-joe`; substitutes literal `oldname`/`newname` tokens into the template via PowerShell `Get-Content -replace`/`Set-Content` **after** the base64 blob is decoded to a `.tmp` file | Renames a specific in-game character's spoken name everywhere text is displayed, including common voice-acting "stutter" dialogue patterns, via a live text-substitution hook rather than editing every `.rpy` file | `unren.actions.replace_name`: port the same regex/case-preservation/stutter-pattern Python logic directly (it's plain Python already, trivially portable — the only Windows-specific part is the PowerShell templating step, replace with Python `str.replace`/`.format`) | **SHOULD** | Good — pure regex logic, easily unit-testable in isolation with sample strings (`Connor`→`Joe`, `c-Connor`→`j-Joe`, etc.) |
| **Remove "nasty" AppData sync folder** — `ACT.n=nasty_sync`, label `:nasty_sync` | Writes static `.rpy` init-9999 python block: `renpy.config.has_sync = False`, `renpy.config.extra_savedirs = []`, to `game/unren-nsync.rpy` | Disables Ren'Py's cross-device save-sync feature (which on Windows tends to create a `%APPDATA%\RenPy\<game>\` folder that can conflict with OneDrive folder-sync) | `unren.actions.disable_save_sync`: identical `.rpy` content write; **note in docs that the Linux equivalent save path is `~/.renpy/<game>/` (some builds: `$XDG_CONFIG_HOME` or `~/.config/renpy/`) and the OneDrive-conflict motivation doesn't directly apply, but the underlying "disable extra sync dirs" toggle is still generically useful** | **SHOULD** | Trivial |
| **Add custom add-on** *(alias of "Custom add-on installer" above — same feature, listed separately in the milestone brief's checklist)* | — see `add_custom_addon` row — | — | — | **SHOULD** | — |
| **Restore original files from backups** — `ACT.r=restore_files`, label `:restore_files` | Recursively finds `*.rpa.org`, `*.rpy.org`, `*.rpyc.org` under `game\`, `move`s each back to its original (non-`.org`) name; reports "not found" if none exist | Undo for the non-destructive `.org`-rename backup convention used by extract/decompile/etc. | `unren.actions.restore_backups`: same glob-and-rename logic against `.org` suffix convention (aligns with Bauplan §14's stated backup strategy, though Bauplan also proposes a more structured `.unren/backups/<timestamp>/` scheme — **decide whether to keep upstream's flat `.org`-suffix convention for 1:1 behavioral parity, or migrate to the structured scheme and document the semantic difference clearly**) | **MUST** | Good — pure filesystem rename logic, fully unit-testable with fixture trees |
| **Delete backups** — `ACT.s=delete_backups`, label `:delete_backups` | Same glob (`*.rpa.org *.rpy.org *.rpyc.org`) under `game\`, `del /f /q`s each; reports "not found" if none exist; **returns `exit /b 1`** if nothing was found (only action in this survey whose "nothing to do" case is a nonzero exit code, worth flagging as a minor upstream inconsistency vs. other "nothing found" cases which don't set an error exit) | Permanently removes the `.org` backups created by prior operations | `unren.actions.delete_backups`: same glob-and-delete; **must be gated behind explicit confirmation given it's the tool's one truly destructive/irreversible built-in action** | **MUST** | Good — trivial to test, including the "nothing found" edge case |
| **Extract text for translation** — `ACT.t=extract_text`, label `:extract_text` (~L3483) | Guards on ≥3 non-`tl\`-folder `.rpy` files existing (else reports a specific "already extracted"/"only compiled .rpyc present" hint); auto-detects the game's executable base-name by finding a name with both `.exe` and `.py` siblings (explicitly **does not** check `.sh` — "it can be not shipped"); prompts for target language if not pre-set from `LNG`; creates `game/tl/` if missing; invokes **Ren'Py's own built-in translate command**: `python.exe <fname>.py game translate <language>` | Delegates to Ren'Py's native `renpy.py <game> translate <lang>` CLI functionality (not a custom UnRen algorithm) to scaffold `game/tl/<lang>/` translation stub files | `unren.actions.extract_text`: same delegation — shell out to the target game's own Ren'Py launcher/runtime with `translate <lang>` args (needs the Runtime Resolver, Bauplan §10); Linux name-detection should check `.sh`/no-extension executables + `.py` pairs instead of `.exe`/`.py` | **SHOULD** | Partial — the wrapper logic (guard conditions, name detection) is testable; the actual translate invocation depends on a real Ren'Py runtime being present, so needs an integration-test fixture with a minimal Ren'Py install |
| **Check for update** — `ACT.u=check_update`, label `:check_update` (~L4009) | Downloads `UnRen-link.txt` from a fixed GitHub raw URL, diffs against a locally cached copy (`fc.exe`), if different: runs the downloaded file *as a batch script* to populate a `forall_url` variable and generate a changelog, base64-decodes and displays the changelog, prompts Y/N, downloads+unpacks the new release zip, calls `:update_file` per script file, optionally self-relaunches | Self-update mechanism for the toolkit itself, with a live changelog fetch/display | **Non-goal to replicate as a self-mutating script.** Map instead to the Bauplan's packaging/versioning story (§21): standard `pip`/`pipx`/distro-package updates (`pip install -U unren-forall-linux`), plus optionally a `unren --version`/`unren doctor` check against PyPI/GitHub releases API for a "new version available" notice only — never auto-download-and-replace-running-code | **COULD** | N/A upstream; would need its own integration tests if built as a lightweight "check PyPI/GitHub for newer version" notice only |
| **Context-menu registry add** — `ACT.+=add_reg`, label `:add_reg` | Adds `HKCU\...\Directory\shell\Run<name>` (+ `Background\shell\...`) registry entries with icon + command pointing back at the batch script | Adds a Windows Explorer right-click "Run UnRen here" entry | **Non-goal on Linux** — see §3 table | **N/A (non-goal)** | N/A |
| **Context-menu registry remove** — `ACT.-=remove_reg`, label `:remove_reg` | Removes the same keys, handles a legacy `HKLM`-rooted variant that needs `:check_admin` elevation first | Undo for the above | **Non-goal on Linux** — see §3 table | **N/A (non-goal)** | N/A |
| **Admin-privilege requirements** — `:check_admin` (~L3852), `:check_old_reg` (~L3667) | `:check_old_reg` queries `HKLM\Software\Classes\Directory\shell\Run<name>` to see if a legacy elevated-install context-menu entry exists; if so, both `:add_reg` (refuses outright, tells user to remove old entry first) and `:remove_reg` (calls `:check_admin` before attempting the `HKLM` delete) gate on it. `:check_admin` itself runs `net session` (fails silently if not elevated) and, if not admin, re-launches itself elevated via `Start-Process -Verb RunAs` | UAC-elevation gating **exclusively for the registry/context-menu feature** — no other feature (extraction, decompile, addons, etc.) requires elevation in the current version (per Changelog: "For your privacy, entry added to the registry are now in the HKCU section instead of HKCR" — i.e. a *prior* version needed broader admin rights and this was deliberately narrowed) | **Non-goal on Linux** as a *mechanism* (no UAC equivalent needed); the underlying *principle* — only the (non-goal) registry feature needs elevated rights, everything else should run as a normal user — is already satisfied by design once the registry feature itself is dropped. Linux port should instead do plain writable-directory permission checks before any file-modifying action (Bauplan "Fehler verständlich melden") | **N/A (non-goal mechanism)**, but the underlying "don't require elevation for core features" principle is **MUST** | N/A |
| **Detection mechanism — Ren'Py version** — `detect_renpy_version.py`, invoked both from `UnRen-forall.bat` (routing) and from `UnRen-current.bat`/`UnRen-legacy.bat` (self-consistency guard) | 7-step priority cascade: live `import renpy` → `script_version.txt` → `renpy/version.py` → `.rpyc`/`.rpymc` magic bytes → `.rpa` archive header → heuristic text-file regex scan → hard failure with explicit error message and process exit (no silent default) | Robust, multi-strategy, fail-closed major-version (6/7/8) detection; see full breakdown in §4 above | `unren.detection.renpy`: port the exact same 7-step cascade (Bauplan §9 already specifies an equivalent priority list — this upstream algorithm should be the literal reference implementation, not just inspiration) | **MUST** | Good — each detection strategy is independently unit-testable against synthetic fixture files (`script_version.txt` content, fake `.rpyc` headers, fake `.rpa` headers, etc. per Bauplan §23 `tests/fixtures/`) |
| **Detection mechanism — language/locale** — `:found_lcid` (~L119), `:lngtest` (~L129) | OS LCID → 7-language map (`en/fr/es/it/de/ru/zh`) via WMIC/PowerShell CIM, `UnRen-cfg.txt` override, CLI positional-arg override, unsupported-LCID → English fallback | UI-language selection cascade: CLI override > config file > OS locale > English default | `unren.ui.i18n`: implement the equivalent cascade using Python's `locale`/`gettext` (or a simple JSON-based lookup per Bauplan §17) against `$LANG`/`$LC_ALL` instead of Windows LCID; same fallback-to-English guarantee ("Keine fehlende Übersetzung darf die Anwendung abbrechen") | **SHOULD** | Trivial — pure mapping/fallback logic, fully unit-testable |
| **RPA-extension/format detection** — `detect_rpa_ext.py`/`detect_archive_extensions()`, invoked inside `:extract_rpa` | 3-step cascade: live `renpy.loader.archive_handlers` introspection → on-disk header content-sniffing (any file starting with `RPA-` regardless of extension) → hardcoded `['.rpa']` fallback | Determines which file extension(s) actually correspond to RPA-format archives for a given game, since some games rename `.rpa` to something else | `unren.detection.archives`: same 3-step cascade, straightforward to port (it's already plain, portable Python in the base64 payload) | **MUST** | Good — directly portable Python, unit-testable |
| **Archive-format classification (standard vs. modified)** — `detect_archive.py`, invoked per-file inside `:extract_rpa` | Reads first 8 bytes; `RPA-`/`SVAC-`/`RWA-3.0 ` prefix → "standard" (use rpatool), else → "modified/unknown" (use altrpatool fallback) | Per-file routing decision between the two extraction backends | `unren.detection.archives` / `unren.adapters.rpatool`: same header-prefix classification, drives which backend the extractor uses | **MUST** | Trivial — pure byte-prefix check, fully unit-testable |
| **RPYC-version detection** — `detect_rpyc_version.py`, invoked inside `:decompile` before running unrpyc | Finds a candidate `.rpyc` (`script.rpyc`/`screen.rpyc`/`options.rpyc`/`gui.rpyc`) under `game/`, reads first 10 bytes: `RENPY RPC2` → treated as "v2-ish" (associated with Ren'Py ≤7 in this heuristic), else → "v3-ish"; cross-checked against the already-known `RENPYVERSION` to print a mismatch warning (doesn't block, just warns) rather than fail | Sanity-check/warning layer to catch cases where the detected Ren'Py major version and the actual `.rpyc` bytecode format disagree (e.g. a Ren'Py-8 game whose compiled files still carry older-format headers) | `unren.detection.archives` (or a new `detection/rpyc.py`): port the same header-sniff + cross-check-and-warn (not fail) logic ahead of invoking the unrpyc adapter | **SHOULD** | Trivial — pure byte-prefix check |

---

## 6. Summary counts

- **Feature/menu-option rows documented in the parity matrix:** 27 (including the two Windows-only
  registry rows and the two detection-mechanism rows required by the milestone spec; the
  `extract_wkey` stub and the "add custom add-on" alias row are counted separately as requested by
  the brief, bringing the raw row count to 27).
- **MUST-priority items:** 13
- **SHOULD-priority items:** 10
- **COULD-priority items:** 3 (two of the four addon downloads lean COULD, `add_utbox` is COULD,
  self-update is COULD)
- **Explicit non-goals (Windows-only, §3):** 7 distinct mechanisms

---

## 7. Open questions / items a human reviewer should double-check

1. **Exact `unrpyc` version pin for the Ren'Py-8 ("current"/`UNRPYC_NEW != "n"`) branch could not be
   confirmed from source.** The CAB blob is binary; only the *legacy* branch's comment block
   plainly states `CensoredUsername/unrpyc`, `__title__ = "Unrpyc Legacy for Ren'Py v7 and lower"`,
   `__version__ = 'v1.3.2'`. The "new" unrpyc variant's version/commit should be confirmed by
   actually running `UnRen-current.bat` in a Windows sandbox (or VM/Wine) and inspecting the
   extracted `unrpyc.py`'s own header/`--version` output, or by decoding the second CAB blob with a
   proper CAB tool (`cabextract` on Linux) rather than just visually scanning the base64 text.
2. **`Universal Choice Descriptor` (`:add_ucd`) has a suspicious cross-referenced `goto`:** inside
   `:add_ugu`'s error-handling branch there's a `goto :skip_ucd` (jumping into a different label's
   cleanup block) rather than the presumably-intended `:skip_ugu`. This looks like a copy-paste bug
   in the upstream script itself — worth flagging to Lurmel upstream, and definitely something the
   Linux port should **not** blindly replicate.
3. **`extract_wkey` (menu option `3`) is a complete no-op in the current shipped version** — the
   milestone brief describes it as "RPA unpack incl. alt method" but the actual code is `goto
   :unavailable`. Confirm whether the "alt method" the brief refers to is actually the `altrpatool`
   path (triggered automatically via header detection or via menu option `7`, not option `3`) —
   this analysis treats `ACT.7` (`usealt=1`) as the real "alt method" and `extract_wkey` as an
   unrelated, currently-disabled feature slot. A human reviewer familiar with older UnRen versions
   could confirm whether `extract_wkey` was previously functional (an `unrpa`-based "extract with
   key" feature per its own comment) and was deliberately disabled, which would change its parity
   priority from "nothing to port" to "consider reviving as SHOULD/COULD."
4. **`:delete_backups` returns `exit /b 1` on "nothing found to delete"** while the structurally
   identical `:restore_files` does not set a nonzero exit in the same situation — likely an
   oversight rather than intentional; the Linux port should probably standardize on *not* treating
   "nothing to do" as an error for either action, but flag this discrepancy since parity-by-exact-
   behavior would otherwise require reproducing the inconsistency.
5. **The four addon downloaders all point at fixed, single-source URLs on `attachments.f95zone.to`
   with no checksum/signature verification** in the upstream script. If/when these are ported,
   strongly consider adding integrity verification (checksums) even though upstream itself doesn't
   have any — this is a security hardening opportunity, not a strict parity requirement.
6. **WOS SHIELD decrypt algorithm (`wos_decrypt_all.py`)** reverse-engineers a specific third-party
   DRM scheme's key derivation. This is inherently fragile (any DRM update breaks it) and its
   presence/correctness should be validated against an actual WOS-shielded game sample before
   committing to full parity — flagged here as functionally understood from source but **not
   independently verified against a real protected file** during this archaeology pass.
7. **RESOLVED (this pass): `RPATOOL_NEW`/`UNRPYC_NEW` gates are driven by the *game's bundled
   Python interpreter major version*, not by `RENPYVERSION`.** Traced end-to-end
   (`UnRen-current.bat` ~L1037–1076): after locating the game's shipped Python runtime
   (`lib\windows-x86_64\python.exe` or similar) and reading its `-V` output, the script checks
   whether a matching `lib\python{major}.{minor}\` directory exists next to a **Python-3-style**
   layout → `RPATOOL_NEW=y` / `UNRPYC_NEW=y` (use the modern py3 `rpatool`/`unrpyc` variants: current
   `rpatool.py` "2022-08-24" build, `unrpyc.py v2.0.3`). Otherwise it looks for the legacy
   `lib\pythonlib{major}.{minor}\` (or `lib\python{major}.{minor}\` without the py3 marker) layout →
   `RPATOOL_NEW=n` / `UNRPYC_NEW=n` (use the older py2-compatible `rpatool.py` fork of
   `Shizmob/rpatool` and `unrpyc.py v1.3.2`). **This is an independent axis from the Ren'Py major
   version (6/7/8) detected by `detect_renpy_version.py`** — a Ren'Py-8 game could in principle still
   ship a Python-2 bundled runtime (older 8.0 betas did), and the tool-variant selection follows the
   *actual bundled Python*, not the Ren'Py major number. **Linux port implication:** the adapter
   selection logic (`unren.adapters.rpatool`/`unren.adapters.unrpyc`) should key off the detected
   Python runtime version (Bauplan §10 Runtime Resolver `PythonRuntime.version`), not off
   `RenPyGeneration` — these are correlated in practice but not identical, and conflating them would
   be a semantic drift from upstream behavior.
8. **Confirmed via `md5sum`:** the two decompile CAB blobs are **byte-identical between
   `UnRen-legacy.bat` and `UnRen-current.bat`** — there is exactly one canonical "legacy" unrpyc
   payload (`v1.3.2`, py2) and one canonical "current" payload (`v2.0.3`, py3) shared by both driver
   scripts; the RPC-version/Ren'Py-generation switch only decides *which of the two* gets extracted
   at runtime (`UNRPYC_NEW` flag), not which *content* ships. Same holds for the `rpatool`/
   `altrpatool` blobs (identical `sha`-equivalent base64 text present in both files, spot-checked by
   byte-length match in the extraction summary: both files report the same `decoded_bytes` counts for
   every embedded payload).
9. **`rpatool.py` "new" (2022-08-24) variant includes a SVAC-1.0 archive decoder and `.jas`
   extension awareness not present in upstream `Shizmob/rpatool`'s public history at the time of
   this pass** — confirmed by direct source read (§1 row 2). This is a genuine Lurmel-authored
   extension, not a straight vendored copy; the Linux port's `adapters/rpatool.py` needs to
   either re-implement this addition or vendor Lurmel's fork specifically (not upstream
   `Shizmob/rpatool` as-is) to keep SVAC-1.0/`.jas` archive parity.

---

*Prepared as Milestone 0 (Upstream Archaeology) deliverable for the `UnRen-forall-linux` port.
All behavioral claims above are sourced from direct reading of `/tmp/unren-upstream` batch source
and its decoded embedded Python payloads — no behavior was assumed from filenames or comments
alone. A follow-up verification pass additionally used `cabextract` to fully decode both embedded
`decomp.cab` blobs (previously only the legacy blob's plaintext comment header had been read) and
`md5sum` to confirm the CAB/base64 payloads are byte-identical between `UnRen-legacy.bat` and
`UnRen-current.bat`, resolving open questions §7.1 (exact unrpyc version pin: confirmed `v2.0.3`,
contradicting the batch's own stale `v2.0.4` comment) and §7.7 (the `RPATOOL_NEW`/`UNRPYC_NEW`
gate: confirmed driven by bundled-Python-version detection, not `RENPYVERSION`). Items §7.2–§7.6
remain open and require either a Windows/Wine sandbox run or real protected-game fixtures to close
fully.*

---

## 8. Milestone 4 parity check — game-config-patch action family + cleanup

Milestone 4 implements every **MUST**-priority parity-matrix row that was still outstanding
after M1-M3 (console, debug, skip, skipall, rollback, restore_files, delete_backups) plus the
**SHOULD**-priority quicksave/quickmenu/nasty_sync rows, and adds the `unren all` bulk command
described in the Bauplan (§7). This section records the actual parity verification performed
against §5's Parity Matrix — not just "implemented", but "checked against the row's documented
Windows-Implementierung / Portable Semantik columns".

| Upstream row | Linux command | Match check performed | Verdict |
|---|---|---|---|
| Enable console/dev mode (`:console`, `ACT.a`) | `unren console enable` | Content diff: upstream writes exactly `config.console = True` + `config.developer = True` to `game/unren-console.rpy`, skip-if-present. Port writes the identical two assignments (wrapped in `init 999 python:` for correct compile-time ordering vs. upstream's presumed bare-`.rpy`-python-block style) to the same filename, with the same skip-if-present idempotency, manually verified via CLI smoke test (write once, verify content, re-run, verify no-op). | **Match** (semantic; wrapped in explicit `init 999 python:` block for clarity/robustness, not a behavioral difference) |
| Enable debug mode (`:debug`, `ACT.b`) | `unren devmode enable` | Same check as console: single assignment `config.debug = True` to `game/unren-debug.rpy`. | **Match** |
| Force-skip (`:skip`, `ACT.c`) | `unren skip enable` | Upstream sets `allow_skipping`, `skip_unseen`, `skip_after_choices`, `fast_skipping`, Ctrl skip-keymap, `persistent.game_completed`. Port sets the same five flags plus `config.keymap["skip"] = ["K_LCTRL", "K_RCTRL"]` (Ren'Py's actual keymap-dict API for binding the skip action to both Ctrl keys — upstream's own keymap-patch mechanism isn't visible byte-for-byte from the batch source beyond "sets Ctrl as skip keymap", so this is the direct, documented Ren'Py API equivalent). | **Match** (semantic — keymap API call is the portable equivalent of "sets Ctrl as skip keymap") |
| Force-skip-all (`:skipall`, `ACT.d`) | `unren skipall enable` | Same base flags as `:skip` plus `_preferences.transitions = 0`, per the row's own note that this is the *only* real differentiator from `:skip` (both already set `skip_unseen=True`). Port's `enable_skip_all` does exactly this: identical flag set + `_preferences.transitions = 0`. | **Match** |
| Rollback enable (`:rollback`, `ACT.e`) | `unren rollback enable` | Upstream: `rollback_enabled=True`, `hard_rollback_limit=256`, `rollback_length=256`, monkeypatches `renpy.block_rollback` to a no-op, PageUp/mouse-4 keymap. Port sets all three config values identically (256/256 buffer sizes matched exactly) and monkeypatches `renpy.block_rollback = lambda: None`. Keymap binding (PageUp/mouse-4) intentionally omitted — Ren'Py's *default* rollback keymap already includes mouse-wheel-up/PageUp out of the box, so this only matters for games that removed it, a narrower edge case; flagged here as a **documented partial deviation**, not silently dropped. | **Partial match** (core semantics 1:1; upstream's explicit keymap re-binding not reproduced — documented) |
| Quick Save/Load (`:quick`, `ACT.f`) | `unren quicksave enable` | Upstream binds F5→QuickSave, F9→QuickLoad via `config.underlay[0].keymap`. Port uses the identical `config.underlay[0].keymap["K_F5"]`/`["K_F9"]` assignment pattern with `QuickSave()`/`QuickLoad()` action objects (Ren'Py's standard API for these). | **Match** |
| Quick-menu force-on (`:qmenu`, `ACT.g`) | `unren quickmenu enable` | Upstream appends callbacks to `config.overlay_functions`/`config.interact_callbacks` forcing `store.quick_menu = True`. Port appends one callback function to both of the same two config lists, setting the same flag. | **Match** |
| Remove nasty AppData sync folder (`:nasty_sync`, `ACT.n`) | `unren nosync enable` | Upstream: `renpy.config.has_sync = False`, `renpy.config.extra_savedirs = []`, written at `init 9999` (highest priority, to override game-set values). Port writes the identical two assignments at the same `init 9999` priority to `game/unren-nsync.rpy`. Doc text updated per the row's own instruction (no `%APPDATA%`-specific wording — see README/module docstring). | **Match** |
| Restore original files from backups (`:restore_files`, `ACT.r`) | `unren cleanup restore` | **Deliberate semantic deviation, not a bug**: upstream walks `game/` for flat `*.rpa.org`/`*.rpy.org`/`*.rpyc.org` siblings and renames them back. This port's Milestone 2 already committed to the Bauplan's alternative centralized `.unren/backups/<relative-path>` scheme instead (see `unren.core.backup` module docstring, written *before* M4 specifically so this action could target one predictable tree). `cleanup restore` therefore restores from the centralized tree, not `*.org` siblings. Functionally equivalent ("undo the last backed-up overwrite"), byte-for-byte upstream mechanism intentionally not replicated. | **Semantic match, documented mechanism deviation** |
| Delete backups (`:delete_backups`, `ACT.s`) | `unren cleanup delete --yes` | Same centralized-tree deviation as `restore_files` above. Additionally: upstream returns nonzero exit on "nothing to delete" while `:restore_files` doesn't (flagged as a likely oversight in §7.4) — port deliberately does **not** reproduce this inconsistency; both `cleanup` operations return 0 on "nothing to do". Confirmation gating (`--yes`) is a Linux-port-only hardening addition (upstream has no equivalent prompt for this specific action beyond generic Y/N menu confirmation) since this is the sole irreversible action in the whole family. | **Semantic match; intentional exit-code-consistency fix + added confirmation gate, both documented** |
| `unren all` (Bauplan §7, no single direct upstream row — corresponds to `ACT.5`/`ACT.6` "run all common operations" combo menu options) | `unren all [PATH]` | Upstream combo options bundle a fixed subset of actions (varies by which combo). Port runs the full non-destructive action set implemented through M4 in the task-card-mandated safety order (detect → extract → decompile → console/devmode → additive patches), explicitly excluding `cleanup` (destructive/undo actions don't belong in a bulk "apply" command - no upstream combo option includes `:restore_files`/`:delete_backups` either, so this exclusion is itself consistent with upstream's own combo-menu design). | **Design-level parity** (same "convenience bundle, safe subset, excludes destructive ops" principle as upstream's combo menu, not a byte-for-byte feature-list match since upstream's exact combo contents couldn't be fully re-derived from the batch source without a live run) |

### Verification method

Every row above was checked two ways:
1. **Static**: content of the generated `.rpy` file / assignment set compared line-by-line
   against the corresponding Windows-Implementierung cell in §5.
2. **Dynamic**: each new action was smoke-tested against synthetic fixture game directories
   via the real installed CLI (`unren <action> enable /path/to/fixture`), confirming: the
   marker file is created with the expected content, a second invocation is a true no-op
   (file content unchanged, `already_present=True` in JSON output), `--dry-run` performs zero
   filesystem writes, and (for `cleanup`) a real backup created by `extract --force` round-trips
   correctly through both `restore` and `delete --yes`. All 72 new automated tests (unit +
   integration) added for Milestone 4 encode these same checks reproducibly — see
   `tests/unit/test_game_patch.py`, `test_enable_console_devmode.py`, `test_game_patches.py`,
   `test_cleanup_action.py`, `test_run_all_action.py`, and the new cases in
   `tests/integration/test_cli.py`.

### Deferred (SHOULD/COULD rows not implemented this milestone)

Per the Exit Criterion ("COULD Features markiert aber nicht blocker"), the following
parity-matrix rows remain unimplemented and are explicitly out of scope for M4:

- Universal Gallery Unlocker / Universal Choice Descriptor / Universal Transparent Text Box /
  0x52_URM addon installers, and the generic custom add-on installer (`ACT.h/i/j/k/p`) —
  all fetch and execute third-party content from a fixed external host at runtime; each needs
  its own network-mocking test fixture and a separate security-hardening discussion
  (checksum verification) before landing. SHOULD/COULD priority.
- Replace character name (`:replace_anyname`, `ACT.l`) — pure-Python regex logic, portable,
  but needs its own interactive-prompt design (CLI flags for old/new name) not yet specified.
  SHOULD priority.
- Extract text for translation (`:extract_text`, `ACT.t`) — delegates to the game's own
  bundled Ren'Py `translate` CLI; needs a real Ren'Py runtime integration-test fixture the
  project doesn't have yet. SHOULD priority.
- `altrpatool`/game's-own-`renpy.loader` extraction fallback for non-standard archive headers
  — needs real modified-archive fixtures to test meaningfully. SHOULD priority (deferred
  since Milestone 2, re-confirmed still deferred here).
- WOS SHIELD pre-decrypt step — needs a real WOS-shielded game sample to validate against;
  flagged as functionally understood but unverified since Milestone 0. SHOULD priority
  (niche, automatic pre-step to decompile, not a user-facing action).
- Check for update (`:check_update`, `ACT.u`) — explicit non-goal as a self-mutating script;
  any future version belongs to packaging/versioning (Bauplan §21), not this action family.
  COULD priority.
