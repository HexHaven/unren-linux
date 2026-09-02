"""Archive detection: which .rpa/-like archives exist and what format they use.

Ports the upstream `detect_rpa_ext.py` / `detect_archive.py` hybrid cascade
documented in docs/UPSTREAM-BEHAVIOR.md §1:

    1. If a live `renpy` module is importable, ask
       `renpy.loader.archive_handlers` which extensions it registers.
    2. Otherwise, content-sniff files on disk for known archive header
       prefixes (`RPA-`, `SVAC-`, `RWA-3.0`) regardless of extension.
    3. Hardcoded fallback: assume `.rpa`.

This module only *detects/reports* archives - no extraction (Milestone 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

KNOWN_HEADER_PREFIXES: tuple[tuple[bytes, str], ...] = (
    (b"RPA-3.2", "RPA-3.2"),
    (b"RPA-3.0", "RPA-3.0"),
    (b"RPA-2.0", "RPA-2.0"),
    (b"RPA-1.0", "RPA-1.0"),
    (b"RPAN3.0", "RPAN-3.0"),
    (b"ZiX-12A", "ZiX-12A"),
    (b"ZiX-12B", "ZiX-12B"),
    (b"SVAC-1.0", "SVAC-1.0"),
    (b"RWA-3.0", "RWA-3.0"),
)

FALLBACK_EXTENSIONS = (".rpa",)

HEADER_SNIFF_BYTES = 16


@dataclass
class ArchiveInfo:
    path: Path
    extension: str
    format: str  # one of the KNOWN_HEADER_PREFIXES labels, or "unknown"


def sniff_archive_header(data: bytes) -> str:
    """Classify raw header bytes; returns a format label or "unknown"."""
    for prefix, label in KNOWN_HEADER_PREFIXES:
        if data.startswith(prefix):
            return label
    return "unknown"


def _live_renpy_archive_extensions() -> list[str] | None:
    """Step 1: ask a live renpy.loader for registered archive extensions."""
    try:
        import renpy.loader  # type: ignore

        handlers = getattr(renpy.loader, "archive_handlers", None)
        if not handlers:
            return None
        exts: list[str] = []
        for handler in handlers:
            get_supported = getattr(handler, "get_supported_extensions", None)
            if callable(get_supported):
                exts.extend(get_supported())
        return exts or None
    except Exception:
        return None


def detect_archive_extensions(root: Path) -> list[str]:
    """Cascade: live renpy introspection -> on-disk content sniff -> ['.rpa']."""
    live = _live_renpy_archive_extensions()
    if live:
        return sorted(set(live))

    found: set[str] = set()
    if root.is_dir():
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                with path.open("rb") as fh:
                    head = fh.read(HEADER_SNIFF_BYTES)
            except OSError:
                continue
            if sniff_archive_header(head) != "unknown":
                found.add(path.suffix.lower() or path.name)
    if found:
        return sorted(found)

    return list(FALLBACK_EXTENSIONS)


def find_archives(root: Path) -> list[ArchiveInfo]:
    """Scan `root` for archive files and classify each by content-sniffed header.

    Read-only. Does not require a live renpy import; used by `detect`/`doctor`
    to report what's present regardless of the extension cascade above.
    """
    results: list[ArchiveInfo] = []
    if not root.is_dir():
        return results
    candidate_suffixes = {".rpa", ".rws", ".jas"} | set(FALLBACK_EXTENSIONS)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        looks_like_archive = suffix in candidate_suffixes
        header_fmt = "unknown"
        try:
            with path.open("rb") as fh:
                head = fh.read(HEADER_SNIFF_BYTES)
            header_fmt = sniff_archive_header(head)
        except OSError:
            pass
        if looks_like_archive or header_fmt != "unknown":
            results.append(ArchiveInfo(path=path, extension=suffix, format=header_fmt))
    return results
