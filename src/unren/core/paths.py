"""Path handling helpers.

Kept deliberately small for Milestone 1: normalization/validation helpers
used by detection and the CLI. No mutation.
"""

from __future__ import annotations

from pathlib import Path

from unren.core.errors import PathNotFoundError


def resolve_existing_dir(raw_path: str | Path) -> Path:
    """Resolve `raw_path` to an absolute Path, expanding ~ and symlinks.

    Raises PathNotFoundError if it doesn't exist or isn't a directory.
    """
    p = Path(raw_path).expanduser()
    try:
        resolved = p.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PathNotFoundError(
            f"Path does not exist: {p}", details={"path": str(p)}
        ) from exc
    if not resolved.is_dir():
        raise PathNotFoundError(
            f"Path is not a directory: {resolved}", details={"path": str(resolved)}
        )
    return resolved


def find_upwards(start: Path, *, markers: tuple[str, ...], max_levels: int = 6) -> Path | None:
    """Walk upward from `start` looking for a directory containing any of `markers`.

    Used so detection doesn't strictly depend on cwd/exact path given (Bauplan §8).
    Returns the first matching directory, or None if not found within max_levels.
    """
    current = start
    for _ in range(max_levels + 1):
        for marker in markers:
            if (current / marker).exists():
                return current
        if current.parent == current:
            break
        current = current.parent
    return None


def iter_files_shallow(directory: Path, *, max_depth: int = 3):
    """Yield files under `directory` up to `max_depth` levels deep (read-only walk)."""
    if not directory.is_dir():
        return
    base_depth = len(directory.parts)
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        depth = len(path.parts) - base_depth
        if depth <= max_depth:
            yield path
