"""RPYC file discovery and low-level format classification (Milestone 3).

Milestone 1 already sniffs `.rpyc`/`.rpymc` magic bytes as *one signal* inside
the Ren'Py generation cascade (`unren.detection.renpy.sniff_rpyc_magic`), but
only scans until the first usable match - it never builds a full inventory of
every compiled file in a game tree, and its magic map only distinguishes
major version 6 vs. an ambiguous "7 or 8" bucket (`RENPY RPC1` / `RENPY
RPC2`). This module adds what Milestone 3 (decompilation) actually needs on
top of that:

- `find_rpyc_files`: a full, read-only inventory of every `.rpyc`/`.rpymc`
  file under a game root (mirrors `unren.detection.archives.find_archives`'s
  shape for the RPA side).
- `sniff_rpyc_format`: fail-closed low-level container classification
  (`RPC1` / `RPC2` / `UNKNOWN`) used to decide whether a given file is a
  recognizable Ren'Py-compiled-script container *at all*, before handing it
  to the unrpyc adapter. Unlike the Milestone 1 cascade step (which only
  cares about *Ren'Py major version*), this classification exists purely to
  support fail-closed error reporting: a file whose header we cannot
  recognize as either known RPYC container layout must be reported as an
  error, never silently skipped (task card acceptance criterion).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

RPYC_SUFFIXES = (".rpyc", ".rpymc")

#: Number of leading bytes read when sniffing a file's container format.
#: 10 is enough to cover the "RENPY RPC2" magic; 2 bytes is the minimum
#: needed for the zlib-header heuristic used to recognize RPC1.
HEADER_SNIFF_BYTES = 16

RPC2_MAGIC = b"RENPY RPC2"


class RpycFormat(str, Enum):
    """Low-level RPYC container classification.

    RPC1: Ren'Py 6-era format. No archive header at all - the entire file
        *is* a zlib-compressed pickle blob. Detected via the zlib stream's
        own 2-byte header (CMF/FLG), not a Ren'Py-specific magic string,
        since there isn't one.
    RPC2: Ren'Py 7/8-era format. Starts with the literal magic bytes
        `RENPY RPC2` followed by a small slot table. Ambiguous between
        Ren'Py 7 and 8 by magic bytes alone (both reuse RPC2 - see
        docs/UPSTREAM-BEHAVIOR.md §4 step 4) - resolving that ambiguity is
        `unren.detection.renpy`'s job via the wider multi-signal cascade,
        not this module's.
    UNKNOWN: Neither shape matched. Covers corrupt files, truncated files,
        and genuinely foreign/unsupported formats (e.g. third-party DRM
        wrappers that don't decrypt to a bare zlib/pickle stream, like the
        WOS-shield scheme documented in the parity matrix). Fail-closed:
        callers must treat this as an error condition for that file, never
        silently skip it.
    """

    RPC1 = "rpc1"
    RPC2 = "rpc2"
    UNKNOWN = "unknown"


@dataclass
class RpycFileInfo:
    path: Path
    format: RpycFormat


def _looks_like_zlib_stream(data: bytes) -> bool:
    """Heuristic zlib-stream sniff for RPC1's headerless format.

    A valid zlib stream's first two bytes (CMF, FLG) must satisfy: the
    compression method nibble of CMF is 8 (deflate - the only method zlib
    actually uses), and the 16-bit big-endian value CMF*256+FLG is a
    multiple of 31 (the format's own FCHECK invariant, RFC 1950 §2.2). This
    is what CPython's `zlib.decompress` itself effectively checks before
    attempting real decompression, so it is a reliable, cheap, don't-need-
    the-whole-file sniff - not a guess.
    """
    if len(data) < 2:
        return False
    cmf, flg = data[0], data[1]
    if (cmf & 0x0F) != 8:
        return False
    return (cmf * 256 + flg) % 31 == 0


def sniff_rpyc_format(data: bytes) -> RpycFormat:
    """Classify raw header bytes of a `.rpyc`/`.rpymc` file."""
    if data.startswith(RPC2_MAGIC):
        return RpycFormat.RPC2
    if _looks_like_zlib_stream(data):
        return RpycFormat.RPC1
    return RpycFormat.UNKNOWN


def find_rpyc_files(root: Path) -> list[RpycFileInfo]:
    """Recursively inventory every `.rpyc`/`.rpymc` file under `root`.

    Read-only. Does not raise for individual unreadable files (permission
    errors etc.) - such files are simply omitted, matching
    `unren.detection.archives.find_archives`'s existing tolerance pattern.
    """
    results: list[RpycFileInfo] = []
    if not root.is_dir():
        return results
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in RPYC_SUFFIXES:
            continue
        try:
            with path.open("rb") as fh:
                head = fh.read(HEADER_SNIFF_BYTES)
        except OSError:
            continue
        results.append(RpycFileInfo(path=path, format=sniff_rpyc_format(head)))
    return results
