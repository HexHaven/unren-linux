"""Unit tests for unren.detection.archives (header sniffing / archive discovery)."""

from __future__ import annotations

from pathlib import Path

import pytest

from unren.detection.archives import find_archives, sniff_archive_header


@pytest.mark.parametrize(
    "header,expected",
    [
        (b"RPA-1.0 xxxxxxxxxxxxxxxxxx", "RPA-1.0"),
        (b"RPA-2.0 xxxxxxxxxxxxxxxxxx", "RPA-2.0"),
        (b"RPA-3.0 xxxxxxxxxxxxxxxxxx", "RPA-3.0"),
        (b"RPA-3.2 xxxxxxxxxxxxxxxxxx", "RPA-3.2"),
        (b"RPAN3.0xxxxxxxxxxxxxxxxxxx", "RPAN-3.0"),
        (b"ZiX-12Axxxxxxxxxxxxxxxxxxx", "ZiX-12A"),
        (b"ZiX-12Bxxxxxxxxxxxxxxxxxxx", "ZiX-12B"),
        (b"SVAC-1.0xxxxxxxxxxxxxxxxxx", "SVAC-1.0"),
        (b"RWA-3.0 xxxxxxxxxxxxxxxxxx", "RWA-3.0"),
        (b"totally unrelated bytes", "unknown"),
    ],
)
def test_sniff_archive_header(header: bytes, expected: str) -> None:
    assert sniff_archive_header(header) == expected


def test_find_archives_discovers_rpa_files(renpy6_game: Path) -> None:
    archives = find_archives(renpy6_game)
    assert len(archives) == 1
    assert archives[0].path.name == "archive.rpa"
    assert archives[0].format == "RPA-2.0"


def test_find_archives_classifies_neutron_format(renpy8_game: Path) -> None:
    archives = find_archives(renpy8_game)
    assert len(archives) == 1
    assert archives[0].format == "RPAN-3.0"


def test_find_archives_empty_for_nonexistent_dir(tmp_path: Path) -> None:
    assert find_archives(tmp_path / "does_not_exist") == []


def test_find_archives_empty_when_no_archives(non_game_dir: Path) -> None:
    assert find_archives(non_game_dir) == []
