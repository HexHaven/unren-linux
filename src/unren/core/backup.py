"""Centralized backup helper for mutating actions (Bauplan §14).

Upstream UnRen-forall uses a flat `<file>.org` sibling-rename convention
(docs/UPSTREAM-BEHAVIOR.md §5, `restore_files`/`delete_backups` rows). The
Bauplan additionally proposes a more structured `.unren/backups/` scheme.
This milestone's card explicitly allows either (".unren-backup" or a
centralized ".unren/backups/") — we pick the centralized scheme so that a
single, predictable location can later be targeted by a `restore`/`cleanup`
action (M6+) without having to re-walk the whole game tree for `*.org`
siblings.

Layout: `<game_root>/.unren/backups/<path relative to game_root>`

Backups are only ever created for a destination file that is about to be
overwritten by a mutating action, and only when the caller has explicitly
opted into overwriting (e.g. `--force`). Creating a backup never raises for
the "nothing to back up yet" case (idempotent create semantics) - it raises
only on genuine I/O failure.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from unren.core.errors import OutputPathError

BACKUP_DIR_NAME = ".unren"
BACKUP_SUBDIR_NAME = "backups"


def backups_root(game_root: Path) -> Path:
    return game_root / BACKUP_DIR_NAME / BACKUP_SUBDIR_NAME


def backup_path_for(game_root: Path, target: Path) -> Path:
    """Compute the backup destination for `target` under `game_root`'s backup tree.

    Falls back to a name-mangled flat path if `target` isn't under `game_root`
    (should not normally happen, but must not raise/crash here).
    """
    try:
        rel = target.resolve().relative_to(game_root.resolve())
    except ValueError:
        rel = Path(target.name)
    return backups_root(game_root) / rel


def backup_file(game_root: Path, target: Path) -> Path | None:
    """Copy `target` into the centralized backup tree before it gets overwritten.

    Returns the backup path, or None if `target` doesn't exist yet (nothing to
    back up). Raises OutputPathError on genuine I/O failure.
    """
    if not target.exists():
        return None
    dest = backup_path_for(game_root, target)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, dest)
    except OSError as exc:
        raise OutputPathError(
            f"Could not back up existing file before overwrite: {target} -> {dest}: {exc}",
            details={"source": str(target), "backup": str(dest)},
        ) from exc
    return dest
