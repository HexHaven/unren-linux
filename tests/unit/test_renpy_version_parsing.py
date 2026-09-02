"""Unit tests for the Ren'Py version-string parsers in unren.detection.renpy."""

from __future__ import annotations

import pytest

from unren.detection.renpy import (
    generation_from_major,
    heuristic_scan_text,
    parse_script_version_txt,
    parse_version_py,
    sniff_rpa_header,
    sniff_rpyc_magic,
    RenPyGeneration,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("(6, 18, 3)", 6),
        ("(7, 5, 3)", 7),
        ("(8, 1, 1)", 8),
        ("8", 8),
        ("8.1.1", 8),
        ("  (6, 99)  \n", 6),
    ],
)
def test_parse_script_version_txt_valid(text: str, expected: int) -> None:
    assert parse_script_version_txt(text) == expected


def test_parse_script_version_txt_unparseable_returns_none() -> None:
    assert parse_script_version_txt("not a version at all") is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ('version = "6.18.3"', 6),
        ('version="7.4.11"', 7),
        ("no version here", None),
    ],
)
def test_parse_version_py(text: str, expected) -> None:
    assert parse_version_py(text) == expected


def test_sniff_rpyc_magic_rpc1_is_major_6() -> None:
    assert sniff_rpyc_magic(b"RENPY RPC1" + b"\x00" * 10) == 6


def test_sniff_rpyc_magic_rpc2_is_ambiguous_none() -> None:
    # RPC2 is deliberately ambiguous (7 or 8) at the magic-byte level.
    assert sniff_rpyc_magic(b"RENPY RPC2" + b"\x00" * 10) is None


def test_sniff_rpyc_magic_unknown_returns_none() -> None:
    assert sniff_rpyc_magic(b"NOT A REAL HEADER") is None


@pytest.mark.parametrize(
    "header,expected",
    [
        (b"RPA-1.0 xxx", 6),
        (b"RPA-2.0 xxx", 6),
        (b"RPA-3.0 xxx", 7),
        (b"RPAN3.0 xxx", 8),
        (b"ZiX-12A xxx", 8),
        (b"ZiX-12B xxx", 8),
        (b"NOT-A-HEADER", None),
    ],
)
def test_sniff_rpa_header(header: bytes, expected) -> None:
    assert sniff_rpa_header(header) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Built with Ren'Py 8.1.3", 8),
        ("Built with RenPy 7.4", 7),
        ("engine: renpy-6 legacy build", 6),
        ("nothing relevant here", None),
    ],
)
def test_heuristic_scan_text(text: str, expected) -> None:
    assert heuristic_scan_text(text) == expected


@pytest.mark.parametrize(
    "major,expected",
    [
        (6, RenPyGeneration.LEGACY),
        (7, RenPyGeneration.LEGACY),
        (8, RenPyGeneration.CURRENT),
        (9, RenPyGeneration.CURRENT),
        (None, RenPyGeneration.UNKNOWN),
    ],
)
def test_generation_from_major(major, expected) -> None:
    assert generation_from_major(major) == expected
