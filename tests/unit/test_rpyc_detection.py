"""Unit tests for unren.detection.rpyc (RPYC discovery/format sniffing)."""

from __future__ import annotations

from pathlib import Path

from unren.detection.rpyc import (
    RpycFormat,
    find_rpyc_files,
    sniff_rpyc_format,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "rpyc_samples"


def test_sniff_rpc2_magic() -> None:
    data = (FIXTURES / "current8_options.rpyc").read_bytes()[:16]
    assert sniff_rpyc_format(data) == RpycFormat.RPC2


def test_sniff_rpc2_magic_legacy_sample_too() -> None:
    # Both legacy (7.7) and current (8.2) real samples use the RPC2 archive
    # wrapper - RPC1 is Ren'Py 6-only and predates both these test fixtures.
    data = (FIXTURES / "legacy7_options.rpyc").read_bytes()[:16]
    assert sniff_rpyc_format(data) == RpycFormat.RPC2


def test_sniff_rpc1_synthetic_zlib_stream() -> None:
    data = (FIXTURES / "synthetic_rpc1.rpyc").read_bytes()[:16]
    assert sniff_rpyc_format(data) == RpycFormat.RPC1


def test_sniff_unknown_for_garbage() -> None:
    assert sniff_rpyc_format(b"NOT A REAL RPYC HEADER AT ALL") == RpycFormat.UNKNOWN


def test_sniff_unknown_for_short_data() -> None:
    assert sniff_rpyc_format(b"\x00") == RpycFormat.UNKNOWN
    assert sniff_rpyc_format(b"") == RpycFormat.UNKNOWN


def test_find_rpyc_files_inventories_all_matches(tmp_path: Path) -> None:
    game = tmp_path / "MyGame" / "game"
    game.mkdir(parents=True)
    (game / "script.rpyc").write_bytes((FIXTURES / "current8_options.rpyc").read_bytes())
    (game / "screens.rpymc").write_bytes((FIXTURES / "legacy7_options.rpyc").read_bytes())
    (game / "not_rpyc.txt").write_text("ignore me")

    found = find_rpyc_files(tmp_path / "MyGame")
    names = sorted(f.path.name for f in found)
    assert names == ["screens.rpymc", "script.rpyc"]
    for f in found:
        assert f.format == RpycFormat.RPC2


def test_find_rpyc_files_classifies_unknown_format(tmp_path: Path) -> None:
    game = tmp_path / "MyGame" / "game"
    game.mkdir(parents=True)
    (game / "corrupt.rpyc").write_bytes(b"totally not a real rpyc container")

    found = find_rpyc_files(tmp_path / "MyGame")
    assert len(found) == 1
    assert found[0].format == RpycFormat.UNKNOWN


def test_find_rpyc_files_empty_for_nonexistent_dir(tmp_path: Path) -> None:
    assert find_rpyc_files(tmp_path / "does_not_exist") == []


def test_find_rpyc_files_empty_when_no_matches(tmp_path: Path) -> None:
    game = tmp_path / "MyGame" / "game"
    game.mkdir(parents=True)
    (game / "readme.txt").write_text("nothing here")
    assert find_rpyc_files(tmp_path / "MyGame") == []
