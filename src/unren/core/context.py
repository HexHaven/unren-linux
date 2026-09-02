"""Core dataclasses describing a detected Ren'Py game and Python runtime.

Per Bauplan §8 / §10.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from unren.detection.renpy import RenPyGeneration


@dataclass
class PythonRuntime:
    """A resolved Python interpreter usable to run Ren'Py-adjacent tooling.

    source: "system" if a suitable system-wide `python3`/`pythonX.Y` was used,
            "renpy" if we fell back to the game's own bundled interpreter,
            "unknown" if no runtime could be resolved at all.
    """

    executable: Path | None
    version: str | None
    source: str = "unknown"  # "system" | "renpy" | "unknown"

    @property
    def resolved(self) -> bool:
        return self.executable is not None


@dataclass
class RenPyVersionInfo:
    """Result of the Ren'Py version detection cascade."""

    generation: RenPyGeneration
    major: int | None = None
    method: str | None = None  # which cascade step produced the result
    raw: str | None = None  # raw evidence string, for debugging/--verbose


@dataclass
class ArchiveInfo:
    path: Path
    extension: str
    format: str  # "RPA-1.0" | "RPA-2.0" | "RPA-3.0" | "RPA-3.2" | "SVAC-1.0" | "RWA-3.0" | "unknown"


@dataclass
class GameContext:
    """Structured detection result for a candidate game directory."""

    root: Path
    game_dir: Path | None
    renpy_dir: Path | None
    runtime: PythonRuntime
    renpy_version: RenPyVersionInfo
    python_version: str | None = None
    archives: list[ArchiveInfo] = field(default_factory=list)

    @property
    def is_game(self) -> bool:
        return self.game_dir is not None or self.renpy_dir is not None
