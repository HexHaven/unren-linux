"""Unit tests for the full Ren'Py detection cascade against synthetic fixtures."""

from __future__ import annotations

from pathlib import Path

from unren.detection.renpy import RenPyGeneration, detect_renpy_version


def test_renpy6_fixture_detected_via_script_version_txt(renpy6_game: Path) -> None:
    result = detect_renpy_version(renpy6_game)
    assert result.major == 6
    assert result.generation == RenPyGeneration.LEGACY
    # script_version.txt (step 2) should win over renpy/version.py (step 3).
    assert result.method == "script_version.txt"


def test_renpy7_fixture_detected_via_rpa_header(renpy7_game: Path) -> None:
    result = detect_renpy_version(renpy7_game)
    # RENPY RPC2 magic is ambiguous (skipped), RPA-3.0 header resolves to major 7.
    assert result.major == 7
    assert result.generation == RenPyGeneration.LEGACY
    assert result.method == "rpa-header"


def test_renpy8_fixture_detected_via_rpa_header(renpy8_game: Path) -> None:
    result = detect_renpy_version(renpy8_game)
    assert result.major == 8
    assert result.generation == RenPyGeneration.CURRENT
    assert result.method == "rpa-header"


def test_unknown_when_no_signal_present(non_game_dir: Path) -> None:
    result = detect_renpy_version(non_game_dir)
    assert result.generation == RenPyGeneration.UNKNOWN
    assert result.major is None
    assert result.method is None


def test_version_py_layout_used_when_no_script_version_txt(tmp_path: Path) -> None:
    root = tmp_path / "renpy6_alt"
    (root / "renpy").mkdir(parents=True)
    (root / "game").mkdir(parents=True)
    (root / "renpy" / "version.py").write_text('version = "6.99.14"\n', encoding="utf-8")

    result = detect_renpy_version(root)
    assert result.major == 6
    assert result.method == "renpy/version.py"


def test_rpyc_magic_step_used_when_no_text_files(tmp_path: Path) -> None:
    root = tmp_path / "renpy_rpyc_only"
    game = root / "game"
    game.mkdir(parents=True)
    with open(game / "script.rpyc", "wb") as f:
        f.write(b"RENPY RPC1")
        f.write(b"\x00" * 20)

    result = detect_renpy_version(root)
    assert result.major == 6
    assert result.method == "rpyc-magic"


def test_heuristic_text_scan_fallback(tmp_path: Path) -> None:
    root = tmp_path / "heuristic_only"
    game = root / "game"
    game.mkdir(parents=True)
    (root / "notes.txt").write_text("This build uses Ren'Py 7.4.11 engine.", encoding="utf-8")

    result = detect_renpy_version(root)
    assert result.major == 7
    assert result.method == "heuristic-text-scan"
