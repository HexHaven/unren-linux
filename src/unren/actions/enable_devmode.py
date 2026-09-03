"""`unren devmode enable` action: enable Ren'Py's `config.debug` developer flag.

Upstream: `ACT.b=debug`, label `:debug` (docs/UPSTREAM-BEHAVIOR.md §5). Writes a
static 1-line `.rpy` file (`config.debug = True`) to `game/unren-debug.rpy` if
it doesn't already exist; skips (no-op, not an error) if present. Same
idempotent, additive-only pattern as `enable_console`, deliberately kept as a
separate action/file per upstream's own separate menu slot (`ACT.a` vs
`ACT.b`) - "console" and "debug"/devmode are two independent upstream toggles
that happen to share a mechanism, not one combined feature.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from unren.core.errors import MissingGameDirectoryError
from unren.core.game_patch import PatchResult, apply_patch_file

MARKER_FILENAME = "unren-debug.rpy"

CONTENT = """\
init 999 python:
    config.debug = True
"""


@dataclass
class DevmodeEnableReport:
    game_dir: str
    dry_run: bool
    patch: PatchResult

    @property
    def already_enabled(self) -> bool:
        return self.patch.already_present

    @property
    def applied(self) -> bool:
        return self.patch.applied


def enable(*, game_dir: Path, dry_run: bool = False) -> DevmodeEnableReport:
    """Idempotently write the `config.debug = True` marker file.

    Raises MissingGameDirectoryError (fail-closed) if `game_dir` doesn't
    exist - there is nowhere upstream-compatible to place the patch file.
    """
    if not game_dir.is_dir():
        raise MissingGameDirectoryError(
            f"No game/ directory found to patch: {game_dir}",
            details={"game_dir": str(game_dir)},
        )

    patch = apply_patch_file(game_dir=game_dir, filename=MARKER_FILENAME, content=CONTENT, dry_run=dry_run)
    return DevmodeEnableReport(game_dir=str(game_dir), dry_run=dry_run, patch=patch)
