"""Test-only helper: build synthetic RPA archives (v1/v2/v3/v3.2) with known content.

Not part of the installed package - used only by the test suite to construct
fixtures without needing real (potentially copyrighted) game archives.

Format reference: docs/UPSTREAM-BEHAVIOR.md §1/§5 + shizmob/rpatool source
(see src/unren/adapters/rpatool.py provenance docstring for the same citation).
"""

from __future__ import annotations

import pickle
import zlib
from pathlib import Path

PICKLE_PROTOCOL = 2


def _write_v2_or_v3(path: Path, files: dict[str, bytes], *, version: int, key: int = 0xDEADBEEF) -> None:
    header_len = 25 if version == 2 else 34
    with path.open("wb") as fh:
        fh.write(b"\x00" * header_len)
        offset = header_len
        indexes: dict[str, list[tuple[int, int]]] = {}
        for name, content in files.items():
            fh.write(content)
            if version == 3:
                indexes[name] = [(offset ^ key, len(content) ^ key)]
            else:
                indexes[name] = [(offset, len(content))]
            offset += len(content)
        fh.write(zlib.compress(pickle.dumps(indexes, PICKLE_PROTOCOL)))
        fh.seek(0)
        if version == 3:
            fh.write(f"RPA-3.0 {offset:016x} {key:08x}\n".encode("ascii"))
        else:
            fh.write(f"RPA-2.0 {offset:016x}\n".encode("ascii"))


def _write_v3_2(path: Path, files: dict[str, bytes], *, key: int = 0xDEADBEEF, subkey: int = 0x12345678) -> None:
    """RPA-3.2 differs from v3 only in header shape: two XOR subkeys instead of one.

    ``rpatool``'s reader (mirrored by ``unren.adapters.rpatool``) re-reads the
    raw header *line* (not the pre-parsed magic) and splits it on whitespace:
    ``vals[0]`` is the magic token, ``vals[1]`` the offset, and for version
    3.2 specifically the effective XOR key is derived from ``vals[3:]`` only
    -- i.e. every subkey token *after* the second one, deliberately skipping
    ``vals[2]`` (the first key field). This is a literal quirk of upstream
    rpatool's ``extract_indexes`` (confirmed by reading
    ``shizmob/rpatool``'s source directly), not a design choice of this
    port - v3 uses ``vals[2:]`` (all tokens from the key field onward) but
    v3.2 uses ``vals[3:]`` (all tokens from the *second* key field onward).
    So the fixture must obfuscate offsets with only ``subkey``, matching
    what the reader will actually reconstruct - the leading ``key`` field is
    written to the header for realism but is intentionally never used as
    obfuscation key material by the reader for this format.
    """
    header_len = 43  # magic(8) + offset(16) + space + subkey1(8) + space + subkey2(8) + newline
    effective_key = subkey
    with path.open("wb") as fh:
        fh.write(b"\x00" * header_len)
        offset = header_len
        indexes: dict[str, list[tuple[int, int]]] = {}
        for name, content in files.items():
            fh.write(content)
            indexes[name] = [(offset ^ effective_key, len(content) ^ effective_key)]
            offset += len(content)
        fh.write(zlib.compress(pickle.dumps(indexes, PICKLE_PROTOCOL)))
        fh.seek(0)
        fh.write(f"RPA-3.2 {offset:016x} {key:08x} {subkey:08x}\n".encode("ascii"))


def build_v1_archive(path: Path, files: dict[str, bytes]) -> None:
    """Build a minimal RPA-1.0 (.rpi) fixture: index-only, zero-length entries.

    Real-world RPA-1.0 archives are rare/legacy and (per rpatool's own
    handling) are read as a single headerless zlib+pickle blob covering the
    *entire* file. That means file content and the index share one zlib
    stream, which isn't practically constructible for arbitrary non-empty
    payloads without also reimplementing a full custom container. For
    Milestone 2's parity purposes (detecting/reading the v1 index structure
    correctly) we build a fixture with all-empty file contents - offsets are
    irrelevant when length is 0, so `read()` returns `b""ā for every member,
    letting the extraction/backup/overwrite-protection logic under test still
    exercise a real v1 container end-to-end (member enumeration + writing 0
    empty destination files).
    """
    indexes: dict[str, list[tuple[int, int]]] = {name: [(0, 0)] for name in files}
    path.write_bytes(zlib.compress(pickle.dumps(indexes, PICKLE_PROTOCOL)))


def build_archive(path: Path, files: dict[str, bytes], *, version: str) -> None:
    if version == "RPA-2.0":
        _write_v2_or_v3(path, files, version=2)
    elif version == "RPA-3.0":
        _write_v2_or_v3(path, files, version=3)
    elif version == "RPA-3.2":
        _write_v3_2(path, files)
    elif version == "RPA-1.0":
        build_v1_archive(path, files)
    else:
        raise ValueError(f"unsupported test fixture version: {version}")
