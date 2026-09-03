"""`unren cleanup` action: restore or permanently delete `.unren/backups/`.

Upstream provides two related MUST-priority features (docs/UPSTREAM-BEHAVIOR.md
§5) that both operate on the backup files created by other mutating actions:

    - "Restore original files from backups" (`ACT.r=restore_files`, `:restore_files`):
      undo - move every backed-up file back over its current counterpart.
    - "Delete backups" (`ACT.s=delete_backups`, `:delete_backups`): permanently
      remove the backups, keeping current files as-is.

Upstream's mechanism is a flat `<file>.rpa.org`/`<file>.rpy.org`/`<file>.rpyc.org`
sibling-rename convention, walked recursively under `game/`. This port's
Milestone 2 (`unren.core.backup`) already deliberately chose the Bauplan's
alternative *centralized* scheme (`<game_root>/.unren/backups/<relative path>`)
over the flat `.org`-suffix convention, specifically so a single predictable
location could later be targeted by exactly this action without re-walking the
whole game tree for `*.org` siblings (see `unren.core.backup`'s own module
docstring). This module is that follow-up: it is a **semantic**, not
byte-for-byte, port - "restore every backup" / "delete every backup" - against
the centralized tree instead of upstream's flat convention. This deviation is
deliberate and documented here per this milestone's parity-check requirement.

Fail-closed / no silent skip: both operations report every file they touch (or
fail to touch) in the returned report; a copy/move failure for one file is
recorded as a per-file error and does not silently abort the rest, but it is
never dropped from the report either.

Destructive-action gating: `delete_backups` is the one truly irreversible
action in this whole action family (once deleted, a backup cannot be
recovered). Per the parity matrix's own explicit note, it must be gated behind
an explicit confirmation - `delete_backups()` therefore requires `confirm=True`
from its caller (the CLI maps this to a `--yes` flag) and raises
`ConfirmationRequiredError` otherwise, rather than deleting on a bare
"nothing to do" default.

Exit-code parity note (docs/UPSTREAM-BEHAVIOR.md §7.4): upstream's
`:delete_backups` returns a nonzero exit code when there is nothing to
delete, while the structurally identical `:restore_files` does not - flagged
upstream itself as a likely oversight. This port intentionally does **not**
reproduce that inconsistency: neither operation treats "nothing to do" as an
error condition.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from unren.core.backup import backups_root
from unren.core.errors import ConfirmationRequiredError


@dataclass
class BackupFileResult:
    backup_path: str
    target_path: str
    ok: bool = False
    error: str | None = None


@dataclass
class CleanupReport:
    game_root: str
    operation: str  # "restore" | "delete"
    dry_run: bool
    files: list[BackupFileResult] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return len(self.files)

    @property
    def total_failed(self) -> int:
        return sum(1 for f in self.files if not f.ok)

    @property
    def total_succeeded(self) -> int:
        return sum(1 for f in self.files if f.ok)


def _iter_backup_files(game_root: Path) -> list[Path]:
    root = backups_root(game_root)
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


def restore_backups(*, game_root: Path, dry_run: bool = False) -> CleanupReport:
    """Move every file under `.unren/backups/` back over its original location.

    "Nothing to restore" is not an error - it simply produces an empty report
    (`total_files == 0`), matching upstream's `:restore_files` "not found"
    case (which is also not treated as an error).
    """
    root = backups_root(game_root)
    report = CleanupReport(game_root=str(game_root), operation="restore", dry_run=dry_run)

    for backup_path in _iter_backup_files(game_root):
        rel = backup_path.relative_to(root)
        target = game_root / rel
        entry = BackupFileResult(backup_path=str(backup_path), target_path=str(target))
        if dry_run:
            entry.ok = True  # "would restore" - not a failure, just previewed
            report.files.append(entry)
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, target)
            backup_path.unlink()
            entry.ok = True
        except OSError as exc:
            entry.ok = False
            entry.error = str(exc)
        report.files.append(entry)

    return report


def delete_backups(*, game_root: Path, dry_run: bool = False, confirm: bool = False) -> CleanupReport:
    """Permanently remove every file under `.unren/backups/`.

    Irreversible - requires explicit `confirm=True` (CLI: `--yes`) unless this
    is a dry run (a dry run never deletes anything, so it doesn't need
    confirmation - it exists precisely to preview what *would* be deleted
    before confirming). Raises ConfirmationRequiredError otherwise, rather
    than silently proceeding or silently no-op'ing.
    """
    if not dry_run and not confirm:
        raise ConfirmationRequiredError(
            "Deleting backups is irreversible. Re-run with --yes to confirm, "
            "or --dry-run to preview what would be deleted.",
            details={"game_root": str(game_root)},
        )

    report = CleanupReport(game_root=str(game_root), operation="delete", dry_run=dry_run)

    for backup_path in _iter_backup_files(game_root):
        entry = BackupFileResult(backup_path=str(backup_path), target_path=str(backup_path))
        if dry_run:
            entry.ok = True  # "would delete" - not a failure, just previewed
            report.files.append(entry)
            continue
        try:
            backup_path.unlink()
            entry.ok = True
        except OSError as exc:
            entry.ok = False
            entry.error = str(exc)
        report.files.append(entry)

    return report
