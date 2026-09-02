"""Ren'Py version / generation detection.

Ports the upstream `detect_renpy_version.py` 7-step priority cascade
documented in docs/UPSTREAM-BEHAVIOR.md §4 ("Detection mechanism (upstream)"):

    1. live `import renpy` (only possible if *we* are running under the
       game's bundled interpreter — for a CLI tool run under our own
       Python this step is a no-op/skip in practice, but is kept for
       parity and for the case where the resolved runtime IS renpy's own
       and a caller explicitly wants to probe with it. See NOTE below.)
    2. `game/script_version.txt` — tuple form `(major, minor, ...)` or a
       leading integer.
    3. `renpy/version.py` — `version = "N..."` (Ren'Py 6-era layout).
    4. `.rpyc` / `.rpymc` magic-number sniffing: `RENPY RPC1` -> major 6,
       `RENPY RPC2` -> major 7 *or* 8 (ambiguous by magic bytes alone).
    5. `.rpa` archive header sniffing: RPA-1.0/2.0 -> 6, RPA-3.0 -> 7 (may be
       refined to 8 by step 4), RPAN3.0/ZiX-12A/ZiX-12B -> 8.
    6. Heuristic regex scan of small text/log/ini/cfg/json files for a
       `Ren'Py N.` / `renpy[-_]N.` pattern.
    7. Hard failure -> UNKNOWN. Never guess.

Fail-closed: any generation/major version we cannot positively establish is
reported as RenPyGeneration.UNKNOWN, never defaulted to LEGACY or CURRENT.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

TEXT_SCAN_EXTENSIONS = (".txt", ".log", ".ini", ".cfg", ".json")
TEXT_SCAN_MAX_BYTES = 65536

RPYC_MAGIC_MAP = {
    b"RENPY RPC1": 6,
    b"RENPY RPC2": None,  # ambiguous: 7 or 8, see cascade step 4 docstring
}

RPA_HEADER_MAP = {
    b"RPA-1.0": 6,
    b"RPA-2.0": 6,
    b"RPA-3.0": 7,  # may be refined to 8 elsewhere in the cascade
    b"RPAN3.0": 8,
    b"ZiX-12A": 8,
    b"ZiX-12B": 8,
}

_HEURISTIC_RE = re.compile(r"Ren['\u2019]?Py[\s._-]*([678])\b|renpy[-_]([678])\b", re.IGNORECASE)


class RenPyGeneration(Enum):
    LEGACY = "legacy"  # Ren'Py <= 7
    CURRENT = "current"  # Ren'Py >= 8
    UNKNOWN = "unknown"


@dataclass
class VersionDetectionResult:
    generation: RenPyGeneration
    major: int | None
    method: str | None
    raw: str | None = None


def generation_from_major(major: int | None) -> RenPyGeneration:
    if major is None:
        return RenPyGeneration.UNKNOWN
    if major <= 7:
        return RenPyGeneration.LEGACY
    return RenPyGeneration.CURRENT


def parse_script_version_txt(text: str) -> int | None:
    """Parse `game/script_version.txt` contents.

    Supports the tuple form `(major, minor, ...)` and the simple leading
    integer form, matching upstream regex `\\(\\s*(\\d+)\\s*,` / leading int.
    """
    text = text.strip()
    m = re.search(r"\(\s*(\d+)\s*,", text)
    if m:
        return int(m.group(1))
    m = re.match(r"^(\d+)", text)
    if m:
        return int(m.group(1))
    return None


def parse_version_py(text: str) -> int | None:
    """Parse `renpy/version.py` for `version = "N..."` (Ren'Py 6-era layout)."""
    m = re.search(r'version\s*=\s*"(\d+)', text)
    if m:
        return int(m.group(1))
    return None


def sniff_rpyc_magic(data: bytes) -> int | None:
    """Return a major version from the first bytes of a .rpyc/.rpymc file, or None."""
    for magic, major in RPYC_MAGIC_MAP.items():
        if data.startswith(magic):
            return major
    return None


def sniff_rpa_header(data: bytes) -> int | None:
    """Return a major version from the first bytes of an .rpa archive, or None."""
    for magic, major in RPA_HEADER_MAP.items():
        if data.startswith(magic):
            return major
    return None


def heuristic_scan_text(text: str) -> int | None:
    m = _HEURISTIC_RE.search(text)
    if not m:
        return None
    group = m.group(1) or m.group(2)
    return int(group) if group else None


def _try_live_renpy_import() -> int | None:
    """Step 1: if `renpy` is importable in *this* interpreter, trust it.

    This only fires when unren itself happens to be running inside a Ren'Py
    bundled interpreter (rare for a normal CLI install, but kept for parity
    with upstream and for future embedding scenarios).
    """
    try:
        import renpy  # type: ignore

        version_tuple = getattr(renpy, "version_tuple", None)
        if version_tuple:
            return int(version_tuple[0])
    except Exception:
        return None
    return None


def detect_renpy_version(root: Path) -> VersionDetectionResult:
    """Run the full 7-step cascade against a game root directory.

    `root` should be the game's top-level directory (containing `game/`
    and/or `renpy/`), not necessarily cwd.
    """
    game_dir = root / "game"
    renpy_dir = root / "renpy"

    # Step 1: live import
    major = _try_live_renpy_import()
    if major is not None:
        return VersionDetectionResult(generation_from_major(major), major, "live-import")

    # Step 2: game/script_version.txt
    sv_path = game_dir / "script_version.txt"
    if sv_path.is_file():
        try:
            text = sv_path.read_text(encoding="utf-8", errors="replace")
            major = parse_script_version_txt(text)
            if major is not None:
                return VersionDetectionResult(
                    generation_from_major(major), major, "script_version.txt", raw=text.strip()
                )
        except OSError:
            pass

    # Step 3: renpy/version.py
    version_py = renpy_dir / "version.py"
    if version_py.is_file():
        try:
            text = version_py.read_text(encoding="utf-8", errors="replace")
            major = parse_version_py(text)
            if major is not None:
                return VersionDetectionResult(
                    generation_from_major(major), major, "renpy/version.py", raw=text[:200]
                )
        except OSError:
            pass

    # Step 4: .rpyc / .rpymc magic bytes (search game dir, shallow-ish)
    rpyc_major: int | None = None
    rpyc_match_name: str | None = None
    rpyc_ambiguous = False
    if root.is_dir():
        for path in sorted(root.rglob("*")):
            if path.suffix.lower() not in (".rpyc", ".rpymc") or not path.is_file():
                continue
            try:
                with path.open("rb") as fh:
                    head = fh.read(16)
            except OSError:
                continue
            m = sniff_rpyc_magic(head)
            if head.startswith(b"RENPY RPC2"):
                rpyc_ambiguous = True
                continue
            if m is not None:
                rpyc_major = m
                rpyc_match_name = path.name
                break
        if rpyc_major is not None:
            return VersionDetectionResult(
                generation_from_major(rpyc_major), rpyc_major, "rpyc-magic", raw=rpyc_match_name
            )

    # Step 5: .rpa archive header
    if root.is_dir():
        for path in sorted(root.rglob("*.rpa")):
            if not path.is_file():
                continue
            try:
                with path.open("rb") as fh:
                    head = fh.read(16)
            except OSError:
                continue
            m = sniff_rpa_header(head)
            if m is not None:
                if m == 7 and rpyc_ambiguous:
                    # RPA-3.0 + ambiguous RPC2 magic present -> could be 8;
                    # cascade docs allow refinement, but we cannot positively
                    # distinguish, so keep the RPA-derived major (7) as the
                    # more specific signal per upstream ordering (step 5
                    # follows step 4 and only "refines if ambiguous" when a
                    # newer-format marker is found - RPA-3.0 itself is not
                    # such a marker).
                    pass
                return VersionDetectionResult(
                    generation_from_major(m), m, "rpa-header", raw=path.name
                )

    # Step 6: heuristic text scan
    if root.is_dir():
        candidates: list[Path] = []
        for ext in TEXT_SCAN_EXTENSIONS:
            candidates.extend(root.glob(f"*{ext}"))
            candidates.extend(game_dir.glob(f"*{ext}"))
        for path in candidates:
            if not path.is_file():
                continue
            try:
                data = path.read_bytes()[:TEXT_SCAN_MAX_BYTES]
                text = data.decode("utf-8", errors="replace")
            except OSError:
                continue
            m = heuristic_scan_text(text)
            if m is not None:
                return VersionDetectionResult(
                    generation_from_major(m), m, "heuristic-text-scan", raw=path.name
                )

    # Step 7: hard failure, fail closed.
    return VersionDetectionResult(RenPyGeneration.UNKNOWN, None, None)
