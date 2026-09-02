"""Game directory detection / structure recognition (Bauplan §8).

Given an arbitrary path, determines whether it (or an ancestor/descendant)
looks like a Ren'Py game, locates `game/` and `renpy/` subdirectories, and
assembles a full GameContext by delegating to detection.renpy/python/archives.
Read-only - never mutates anything.
"""

from __future__ import annotations

from pathlib import Path

from unren.core.context import ArchiveInfo as CtxArchiveInfo
from unren.core.context import GameContext, RenPyVersionInfo
from unren.core.errors import NotAGameDirectoryError
from unren.core.paths import find_upwards, resolve_existing_dir
from unren.detection import archives as archives_detect
from unren.detection import python as python_detect
from unren.detection import renpy as renpy_detect

STRUCTURE_MARKERS = ("game", "renpy")
# NOTE: "lib" was deliberately dropped from the upward-search markers (bugfix,
# Milestone 1 verification pass). Almost every Linux system has a top-level
# /lib (commonly a symlink to /usr/lib), so including it here caused
# find_upwards() to walk all the way to "/" and falsely treat the filesystem
# root as a plausible game root for *any* starting path without a game/renpy
# dir in its ancestry - which then made detect_renpy_version()/find_archives()
# recursively scan the entire filesystem via root.rglob("*") and hang.
# "game"/"renpy" are the only markers actually documented as identifying a
# Ren'Py game root; "lib" alone is not a reliable/unique signal for that.


def _find_game_root(start: Path) -> Path:
    """Locate the most plausible game root starting from `start`.

    Priority:
      1. `start` itself, if it directly contains game/ or renpy/.
      2. An ancestor (up to 6 levels) containing game/ or renpy/.
      3. `start` itself as a last resort (so detection can still run and
         report UNKNOWN/absent structure rather than raising).
    """
    if (start / "game").is_dir() or (start / "renpy").is_dir():
        return start
    found = find_upwards(start, markers=STRUCTURE_MARKERS)
    if found is not None:
        return found
    return start


def detect_game(raw_path: str | Path) -> GameContext:
    """Run full detection against `raw_path` and return a GameContext.

    Raises PathNotFoundError if the path doesn't exist. Does NOT raise if the
    path exists but isn't a Ren'Py game - callers should check
    `GameContext.is_game` / `renpy_version.generation == UNKNOWN`.
    """
    start = resolve_existing_dir(raw_path)
    root = _find_game_root(start)

    game_dir = root / "game"
    renpy_dir = root / "renpy"

    version_result = renpy_detect.detect_renpy_version(root)
    runtime = python_detect.resolve_python_runtime(root)
    found_archives = archives_detect.find_archives(root)

    return GameContext(
        root=root,
        game_dir=game_dir if game_dir.is_dir() else None,
        renpy_dir=renpy_dir if renpy_dir.is_dir() else None,
        runtime=runtime,
        renpy_version=RenPyVersionInfo(
            generation=version_result.generation,
            major=version_result.major,
            method=version_result.method,
            raw=version_result.raw,
        ),
        python_version=runtime.version,
        archives=[
            CtxArchiveInfo(path=a.path, extension=a.extension, format=a.format)
            for a in found_archives
        ],
    )


def require_game(raw_path: str | Path) -> GameContext:
    """Like detect_game, but raises NotAGameDirectoryError if nothing was found."""
    ctx = detect_game(raw_path)
    if not ctx.is_game:
        raise NotAGameDirectoryError(
            f"No Ren'Py game structure found at or near: {ctx.root}",
            details={"path": str(ctx.root)},
        )
    return ctx
