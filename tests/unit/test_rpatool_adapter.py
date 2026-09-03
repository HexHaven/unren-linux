"""Unit tests for unren.adapters.rpatool (RPA container reader)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.rpa_builder import build_archive
from unren.adapters import rpatool
from unren.adapters.rpatool import (
    CorruptArchiveError,
    UnsupportedArchiveFormatError,
    open_archive,
)


@pytest.mark.parametrize("version", ["RPA-2.0", "RPA-3.0", "RPA-3.2"])
def test_round_trip_extraction(tmp_path: Path, version: str) -> None:
    files = {
        "script.rpyc": b"\x00hello world" * 10,
        "images/bg.png": bytes(range(256)),
        "audio/theme.ogg": b"OggS" + b"\xff" * 50,
    }
    archive_path = tmp_path / "archive.rpa"
    build_archive(archive_path, files, version=version)

    reader = open_archive(archive_path)
    assert reader.version == version
    assert set(reader.list_names()) == set(files.keys())
    for name, content in files.items():
        assert reader.read(name) == content


def test_v1_archive_detected_and_empty_members(tmp_path: Path) -> None:
    files = {"a.txt": b"", "sub/b.txt": b""}
    archive_path = tmp_path / "archive.rpi"
    build_archive(archive_path, files, version="RPA-1.0")

    reader = open_archive(archive_path)
    assert reader.version == "RPA-1.0"
    assert set(reader.list_names()) == set(files.keys())
    for name in files:
        assert reader.read(name) == b""


def test_multiple_archives_independent(tmp_path: Path) -> None:
    a1 = tmp_path / "one.rpa"
    a2 = tmp_path / "two.rpa"
    build_archive(a1, {"x.txt": b"aaa"}, version="RPA-2.0")
    build_archive(a2, {"y.txt": b"bbb"}, version="RPA-3.0")

    r1 = open_archive(a1)
    r2 = open_archive(a2)
    assert r1.read("x.txt") == b"aaa"
    assert r2.read("y.txt") == b"bbb"
    assert "y.txt" not in r1.entries
    assert "x.txt" not in r2.entries


def test_unicode_and_space_member_names(tmp_path: Path) -> None:
    files = {
        "unicöde/dätei nämé.txt": "hällo wörld".encode("utf-8"),
        "with space/file name.rpyc": b"payload",
    }
    archive_path = tmp_path / "archive.rpa"
    build_archive(archive_path, files, version="RPA-3.0")

    reader = open_archive(archive_path)
    for name, content in files.items():
        assert reader.read(name) == content


def test_paths_with_spaces_and_unicode_dirs(tmp_path: Path) -> None:
    weird_dir = tmp_path / "gäme dir with spaces"
    weird_dir.mkdir()
    archive_path = weird_dir / "arch ïve.rpa"
    build_archive(archive_path, {"f.txt": b"content"}, version="RPA-2.0")

    reader = open_archive(archive_path)
    assert reader.read("f.txt") == b"content"


def test_unknown_header_raises_unsupported_format(tmp_path: Path) -> None:
    archive_path = tmp_path / "weird.rpa"
    archive_path.write_bytes(b"NOTAREALHEADER\n" + b"\x00" * 20)
    with pytest.raises(UnsupportedArchiveFormatError):
        open_archive(archive_path)


def test_neutron_format_raises_unsupported_format(tmp_path: Path) -> None:
    archive_path = tmp_path / "neutron.rpa"
    archive_path.write_bytes(b"RPAN3.0" + b"\x00" * 20)
    with pytest.raises(UnsupportedArchiveFormatError):
        open_archive(archive_path)


def test_missing_file_raises_corrupt_archive_error(tmp_path: Path) -> None:
    with pytest.raises(CorruptArchiveError):
        open_archive(tmp_path / "does_not_exist.rpa")


def test_read_nonexistent_member_raises(tmp_path: Path) -> None:
    archive_path = tmp_path / "archive.rpa"
    build_archive(archive_path, {"a.txt": b"x"}, version="RPA-3.0")
    reader = open_archive(archive_path)
    with pytest.raises(CorruptArchiveError):
        reader.read("does/not/exist.txt")


def test_corrupt_index_raises_corrupt_archive_error(tmp_path: Path) -> None:
    archive_path = tmp_path / "archive.rpa"
    archive_path.write_bytes(b"RPA-3.0 " + b"0" * 16 + b" deadbeef\n" + b"not valid zlib data")
    with pytest.raises(CorruptArchiveError):
        open_archive(archive_path).entries


def test_supported_formats_constant_matches_reader() -> None:
    assert rpatool.SUPPORTED_FORMATS == ("RPA-1.0", "RPA-2.0", "RPA-3.0", "RPA-3.2")
