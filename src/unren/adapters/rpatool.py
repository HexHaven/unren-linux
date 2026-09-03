"""RPA archive reader/extractor adapter.

Provenance
----------
Upstream UnRen-forall (docs/UPSTREAM-BEHAVIOR.md §1) vendors a fork of
`Shizmob/rpatool <https://github.com/shizmob/rpatool>`_ (WTFPL license) as an
inline base64 Python payload rather than a published dependency (rpatool is
not on PyPI). Per Bauplan §12 ("keine undokumentierten Vendor-Blobs") this
module is instead a from-scratch, version-pinned reimplementation of the same
publicly documented RPA container format, written directly against:

- `shizmob/rpatool` reference source (``RenPyArchive.get_version`` /
  ``extract_indexes`` / ``read``), commit as published on the ``master``
  branch, retrieved 2026-09 for this port. Format constants (magic strings,
  XOR-key derivation for v3/3.2, pickle+zlib index encoding) are taken
  directly from that source.
- The Reverse Engineering Wiki's Ren'Py RPA format page
  (https://rewiki.miraheze.org/wiki/Ren%E2%80%99Py_RPA), used to
  cross-check the header byte layout.

Only the "standard" RPA family (v1/.rpi, v2, v3, v3.2) is implemented here —
this is what Milestone 2's acceptance criteria require ("RPA v2/v3"). The
`altrpatool` fallback (importing the game's own bundled ``renpy.loader`` to
read non-standard/obfuscated headers) and the SVAC-1.0/RWA-3.0/RPAN-3.0/ZiX
"neutron" formats are explicitly out of scope for this milestone; archives
sniffed as one of those formats raise `UnsupportedArchiveFormatError` rather
than silently mis-parsing them.

No network access, no subprocess shelling to a real ``rpatool`` binary: this
is a pure-Python, dependency-free reader (stdlib `pickle`/`zlib` only).
"""

from __future__ import annotations

import pickle
import zlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from unren.core.errors import UnrenError

DEFAULT_KEY = 0xDEADBEEF

RPA_1_EXT = ".rpi"
RPA_2_MAGIC = b"RPA-2.0 "
RPA_3_MAGIC = b"RPA-3.0 "
RPA_3_2_MAGIC = b"RPA-3.2 "

# Formats whose *container* structure (pickle+zlib index, XOR obfuscation
# scheme) is understood and implemented by this adapter.
SUPPORTED_FORMATS = ("RPA-1.0", "RPA-2.0", "RPA-3.0", "RPA-3.2")

# Formats detected upstream (unren.detection.archives) but not yet supported
# for extraction by this adapter — raise a clear, actionable error instead of
# guessing at an unimplemented container layout.
KNOWN_UNSUPPORTED_FORMATS = ("RPAN-3.0", "ZiX-12A", "ZiX-12B", "SVAC-1.0", "RWA-3.0")


class RpaError(UnrenError):
    code = "rpa-error"


class UnsupportedArchiveFormatError(RpaError):
    code = "rpa-unsupported-format"


class CorruptArchiveError(RpaError):
    code = "rpa-corrupt-archive"


@dataclass(frozen=True)
class RpaIndexEntry:
    """A single file's location inside an RPA archive."""

    name: str  # archive-internal, POSIX-style relative path
    offset: int
    length: int
    prefix: bytes = b""


def _detect_version(header_line: bytes, *, path: Path) -> str:
    """Classify an RPA container by its first line (mirrors rpatool's get_version)."""
    if header_line.startswith(RPA_3_2_MAGIC):
        return "RPA-3.2"
    if header_line.startswith(RPA_3_MAGIC):
        return "RPA-3.0"
    if header_line.startswith(RPA_2_MAGIC):
        return "RPA-2.0"
    if path.suffix.lower() == RPA_1_EXT:
        return "RPA-1.0"

    for label in KNOWN_UNSUPPORTED_FORMATS:
        if header_line.startswith(label.encode("ascii", "ignore")[:4]):
            raise UnsupportedArchiveFormatError(
                f"Archive format '{label}' is not yet supported for extraction: {path}",
                details={"path": str(path), "format": label},
            )
    raise UnsupportedArchiveFormatError(
        f"Could not recognize the RPA container format of: {path}",
        details={"path": str(path)},
    )


def _normalize_archive_name(name: str) -> str:
    """Archive-internal names are always POSIX-style; normalize just in case."""
    return str(PurePosixPath(name.replace("\\", "/")))


class RpaArchiveReader:
    """Read-only accessor for a single RPA archive's index and file contents.

    Mirrors the read path of ``shizmob/rpatool``'s ``RenPyArchive`` (load +
    extract_indexes + read), without any of its write/create/append support,
    which Milestone 2 does not need.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise CorruptArchiveError(
                f"Archive file not found: {self.path}", details={"path": str(self.path)}
            )
        with self.path.open("rb") as fh:
            header_line = fh.readline()
        self.version = _detect_version(header_line, path=self.path)
        self._entries: dict[str, RpaIndexEntry] | None = None

    @property
    def entries(self) -> dict[str, RpaIndexEntry]:
        if self._entries is None:
            self._entries = self._read_index()
        return self._entries

    def list_names(self) -> list[str]:
        return sorted(self.entries.keys())

    def _read_index(self) -> dict[str, RpaIndexEntry]:
        try:
            with self.path.open("rb") as fh:
                if self.version == "RPA-1.0":
                    # No text header at all: the whole file is the zlib+pickle
                    # index blob (see rpatool's `else` branch of extract_indexes).
                    raw_index = pickle.loads(zlib.decompress(fh.read()), encoding="latin1")
                    key = 0
                else:
                    header_line = fh.readline()
                    parts = header_line.split()
                    offset = int(parts[1], 16)
                    key = 0
                    if self.version == "RPA-3.0":
                        for sub in parts[2:]:
                            key ^= int(sub, 16)
                    elif self.version == "RPA-3.2":
                        for sub in parts[3:]:
                            key ^= int(sub, 16)
                    fh.seek(offset)
                    raw_index = pickle.loads(zlib.decompress(fh.read()), encoding="latin1")
        except (OSError, EOFError, zlib.error, pickle.UnpicklingError, IndexError, ValueError) as exc:
            raise CorruptArchiveError(
                f"Could not read index of archive {self.path}: {exc}",
                details={"path": str(self.path)},
            ) from exc

        entries: dict[str, RpaIndexEntry] = {}
        obfuscate = self.version in ("RPA-3.0", "RPA-3.2")
        for raw_name, parts_list in raw_index.items():
            name = _normalize_archive_name(
                raw_name.decode("utf-8") if isinstance(raw_name, bytes) else raw_name
            )
            first = parts_list[0]
            if len(first) == 3:
                off, length, prefix = first
            else:
                off, length = first
                prefix = b""
            if obfuscate:
                off ^= key
                length ^= key
            if isinstance(prefix, str):
                prefix = prefix.encode("latin1")
            entries[name] = RpaIndexEntry(name=name, offset=off, length=length, prefix=prefix)
        return entries

    def read(self, name: str) -> bytes:
        name = _normalize_archive_name(name)
        if name not in self.entries:
            raise CorruptArchiveError(
                f"File '{name}' not found in archive {self.path}",
                details={"path": str(self.path), "member": name},
            )
        entry = self.entries[name]
        with self.path.open("rb") as fh:
            fh.seek(entry.offset)
            data = fh.read(entry.length - len(entry.prefix))
        return entry.prefix + data


def open_archive(path: Path) -> RpaArchiveReader:
    """Open `path` and classify+index it, raising RpaError subclasses on failure."""
    return RpaArchiveReader(path)
