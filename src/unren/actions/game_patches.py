"""Additional static `.rpy` game-config patch actions (Milestone 4).

Per docs/UPSTREAM-BEHAVIOR.md §5, all of these upstream actions share the
exact same mechanism as `enable_console`/`enable_devmode` (see
`unren.core.game_patch`): write one small, static, idempotent `.rpy` file
into `game/` under a fixed filename, skip (no-op) if already present. They
are grouped in one module - instead of five near-identical
`enable_console.py`-shaped files - because the logic really is that
mechanism, and each row below differs only in filename/content/priority.

Rows implemented here (Priority per parity matrix):
    - enable_skip      MUST    ACT.c=skip     (:skip)
    - enable_skip_all  MUST    ACT.d=skipall  (:skipall)
    - enable_rollback  MUST    ACT.e=rollback (:rollback)
    - enable_quicksave SHOULD  ACT.f=quick    (:quick)
    - enable_quickmenu SHOULD  ACT.g=qmenu    (:qmenu)
    - disable_save_sync SHOULD ACT.n=nasty_sync (:nasty_sync)

Each function returns a `PatchResult` (see `unren.core.game_patch`) and
raises `MissingGameDirectoryError` (fail-closed) if `game_dir` doesn't exist.
"""

from __future__ import annotations

from pathlib import Path

from unren.core.errors import MissingGameDirectoryError
from unren.core.game_patch import PatchResult, apply_patch_file

# --- Force-skip (seen-only) --------------------------------------------------
# Upstream: allow_skipping=True, skip_unseen=True, skip_after_choices=True,
# fast_skipping=True, Ctrl as skip keymap, persistent.game_completed=True.
SKIP_FILENAME = "unren-skip.rpy"
SKIP_CONTENT = """\
init 999 python:
    config.allow_skipping = True
    config.skip_unseen = True
    config.skip_after_choices = True
    config.fast_skipping = True
    config.keymap["skip"] = ["K_LCTRL", "K_RCTRL"]
    persistent.game_completed = True
"""

# --- Force-skip-all (incl. unseen) ------------------------------------------
# Same as :skip plus disabling transitions (_preferences.transitions = 0).
SKIP_ALL_FILENAME = "unren-skipall.rpy"
SKIP_ALL_CONTENT = """\
init 999 python:
    config.allow_skipping = True
    config.skip_unseen = True
    config.skip_after_choices = True
    config.fast_skipping = True
    persistent.game_completed = True
    _preferences.transitions = 0
"""

# --- Rollback enable ---------------------------------------------------------
# Force-enables rollback (undo/scroll-back) with a large history buffer and
# neutralizes renpy.block_rollback() (some games call it to block save-scumming).
ROLLBACK_FILENAME = "unren-rollback.rpy"
ROLLBACK_CONTENT = """\
init 999 python:
    config.rollback_enabled = True
    config.hard_rollback_limit = 256
    config.rollback_length = 256
    renpy.block_rollback = lambda: None
"""

# --- Quick Save/Load enable ---------------------------------------------------
# Binds F5 -> QuickSave, F9 -> QuickLoad regardless of the game's own keymap.
QUICKSAVE_FILENAME = "unren-quicksave.rpy"
QUICKSAVE_CONTENT = """\
init 999 python:
    config.underlay[0].keymap["K_F5"] = QuickSave()
    config.underlay[0].keymap["K_F9"] = QuickLoad()
"""

# --- Quick-menu force-on -----------------------------------------------------
# Forces the quick-menu overlay to always be shown, even on screens that
# normally hide it (e.g. main menu).
QUICKMENU_FILENAME = "unren-qmenu.rpy"
QUICKMENU_CONTENT = """\
init python:
    def _unren_force_quick_menu():
        store.quick_menu = True

    config.overlay_functions.append(_unren_force_quick_menu)
    config.interact_callbacks.append(_unren_force_quick_menu)
"""

# --- Remove "nasty" AppData/save-sync folder ---------------------------------
# Disables Ren'Py's cross-device save-sync feature (upstream motivation: a
# Windows OneDrive folder-sync conflict; kept as a generically useful toggle
# on Linux even though that specific conflict doesn't apply - see
# docs/UPSTREAM-BEHAVIOR.md §3 "nasty_sync" row).
DISABLE_SAVE_SYNC_FILENAME = "unren-nsync.rpy"
DISABLE_SAVE_SYNC_CONTENT = """\
init 9999 python:
    renpy.config.has_sync = False
    renpy.config.extra_savedirs = []
"""


def _apply(*, game_dir: Path, filename: str, content: str, dry_run: bool) -> PatchResult:
    if not game_dir.is_dir():
        raise MissingGameDirectoryError(
            f"No game/ directory found to patch: {game_dir}",
            details={"game_dir": str(game_dir)},
        )
    return apply_patch_file(game_dir=game_dir, filename=filename, content=content, dry_run=dry_run)


def enable_skip(*, game_dir: Path, dry_run: bool = False) -> PatchResult:
    return _apply(game_dir=game_dir, filename=SKIP_FILENAME, content=SKIP_CONTENT, dry_run=dry_run)


def enable_skip_all(*, game_dir: Path, dry_run: bool = False) -> PatchResult:
    return _apply(game_dir=game_dir, filename=SKIP_ALL_FILENAME, content=SKIP_ALL_CONTENT, dry_run=dry_run)


def enable_rollback(*, game_dir: Path, dry_run: bool = False) -> PatchResult:
    return _apply(game_dir=game_dir, filename=ROLLBACK_FILENAME, content=ROLLBACK_CONTENT, dry_run=dry_run)


def enable_quicksave(*, game_dir: Path, dry_run: bool = False) -> PatchResult:
    return _apply(game_dir=game_dir, filename=QUICKSAVE_FILENAME, content=QUICKSAVE_CONTENT, dry_run=dry_run)


def enable_quickmenu(*, game_dir: Path, dry_run: bool = False) -> PatchResult:
    return _apply(game_dir=game_dir, filename=QUICKMENU_FILENAME, content=QUICKMENU_CONTENT, dry_run=dry_run)


def disable_save_sync(*, game_dir: Path, dry_run: bool = False) -> PatchResult:
    return _apply(
        game_dir=game_dir, filename=DISABLE_SAVE_SYNC_FILENAME, content=DISABLE_SAVE_SYNC_CONTENT, dry_run=dry_run
    )
