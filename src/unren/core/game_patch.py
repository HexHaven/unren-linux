"""Shared helper for idempotent, additive-only `.rpy` config-patch files.

Per docs/UPSTREAM-BEHAVIOR.md §5, a whole family of upstream actions (`:console`,
`:debug`, `:skip`, `:skipall`, `:rollback`, `:quick`, `:qmenu`, `:nasty_sync`) share
exactly one mechanism: write a small, static `.rpy` file into `game/` under a
fixed, action-specific filename, *unless that file already exists* - in which
case the action is a no-op (idempotent, not an error). Nothing is ever read
back or content-diffed; presence of the marker file alone gates re-application,
matching upstream's own check-before-write behavior exactly.

This module centralizes that one mechanism so every action built on it (M4)
stays consistent and independently testable instead of five near-identical
file-write implementations drifting apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PatchResult:
    target: str
    already_present: bool
    applied: bool
    dry_run: bool
    content: str

    @property
    def would_apply(self) -> bool:
        """True if a real (non-dry-run) run would have written the file."""
        return not self.already_present


def apply_patch_file(*, game_dir: Path, filename: str, content: str, dry_run: bool = False) -> PatchResult:
    """Write `content` to `<game_dir>/<filename>` unless it already exists.

    Never overwrites an existing marker file (matches upstream's "skip if
    already present" idempotency - re-running the same action twice is always
    safe and a no-op the second time). `dry_run` computes and returns the
    result without touching the filesystem at all.
    """
    if not content.endswith("\n"):
        content += "\n"

    target = game_dir / filename
    already_present = target.exists()
    applied = False

    if not already_present and not dry_run:
        game_dir.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        applied = True

    return PatchResult(
        target=str(target),
        already_present=already_present,
        applied=applied,
        dry_run=dry_run,
        content=content,
    )
