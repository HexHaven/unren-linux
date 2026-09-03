"""`unren console enable` action: enable Ren'Py's built-in developer console.

Upstream: `ACT.a=console`, label `:console` (docs/UPSTREAM-BEHAVIOR.md §5). Writes
a static 2-line `.rpy` file (`config.console = True`, `config.developer = True`)
to `game/unren-console.rpy` if it doesn't already exist; skips (no-op, not an
error) if present. Idempotent, additive-only game-config patch - never reads,
diffs, or removes anything else in the game tree.

Note: upstream's single `:console` label sets *both* `config.console` and
`config.developer` in one file. This module keeps that exact upstream
behavior (1:1 parity) rather than splitting console/developer into two
separate toggles - `enable_devmode` (a distinct upstream action, `:debug`,
`config.debug = True`) is unrelated and separate per the parity matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from unren.core.errors import MissingGameDirectoryError
from unren.core.game_patch import PatchResult, apply_patch_file

MARKER_FILENAME = "unren-console.rpy"

CONTENT = """\
init 999 python:
    config.console = True
    config.developer = True
"""


@dataclass
class ConsoleEnableReport:
    game_dir: str
    dry_run: bool
    patch: PatchResult

    @property
    def already_enabled(self) -> bool:
        return self.patch.already_present

    @property
    def applied(self) -> bool:
        return self.patch.applied


def enable(*, game_dir: Path, dry_run: bool = False) -> ConsoleEnableReport:
    """Idempotently write the console/developer-mode marker file.

    Raises MissingGameDirectoryError (fail-closed) if `game_dir` doesn't
    exist - there is nowhere upstream-compatible to place the patch file.
    """
    if not game_dir.is_dir():
        raise MissingGameDirectoryError(
            f"No game/ directory found to patch: {game_dir}",
            details={"game_dir": str(game_dir)},
        )

    patch = apply_patch_file(game_dir=game_dir, filename=MARKER_FILENAME, content=CONTENT, dry_run=dry_run)
    return ConsoleEnableReport(game_dir=str(game_dir), dry_run=dry_run, patch=patch)
