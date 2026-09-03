"""Unit tests for unren.actions.extract_rpa (planning/execution logic)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.rpa_builder import build_archive
from unren.actions import extract_rpa
from unren.core.errors import OutputPathError
from unren.detection.archives import ArchiveInfo, find_archives


def _make_game(tmp_path: Path) -> Path:
    game_root = tmp_path / "MyGame"
    game_dir = game_root / "game"
    game_dir.mkdir(parents=True)
    return game_root


def test_default_output_dir_is_sibling_unren_extracted(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    out = extract_rpa.resolve_output_root(game_root=game_root, game_dir=game_root / "game", output=None, in_place=False)
    assert out == game_root / "unren-extracted"


def test_custom_output_dir(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    custom = tmp_path / "custom_out"
    out = extract_rpa.resolve_output_root(game_root=game_root, game_dir=game_root / "game", output=str(custom), in_place=False)
    assert out == custom


def test_in_place_uses_game_dir(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    out = extract_rpa.resolve_output_root(game_root=game_root, game_dir=game_root / "game", output=None, in_place=True)
    assert out == game_root / "game"


def test_output_and_in_place_mutually_exclusive(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    with pytest.raises(OutputPathError):
        extract_rpa.resolve_output_root(
            game_root=game_root, game_dir=game_root / "game", output="/tmp/x", in_place=True
        )


def test_dry_run_plans_but_does_not_write(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    archive_path = game_root / "game" / "archive.rpa"
    build_archive(archive_path, {"a.txt": b"hello"}, version="RPA-3.0")
    archives = find_archives(game_root)

    report = extract_rpa.extract(
        game_root=game_root, game_dir=game_root / "game", dry_run=True, archives=archives
    )
    assert report.dry_run is True
    assert report.total_archives == 1
    assert not (game_root / "unren-extracted").exists()
    assert report.archives[0].members[0].member == "a.txt"


def test_real_extraction_creates_output_dir_and_files(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    archive_path = game_root / "game" / "archive.rpa"
    build_archive(archive_path, {"a.txt": b"hello", "sub/b.txt": b"world"}, version="RPA-2.0")
    archives = find_archives(game_root)

    report = extract_rpa.extract(game_root=game_root, game_dir=game_root / "game", archives=archives)
    assert report.dry_run is False
    out_dir = game_root / "unren-extracted"
    assert (out_dir / "a.txt").read_bytes() == b"hello"
    assert (out_dir / "sub" / "b.txt").read_bytes() == b"world"
    assert report.total_extracted_files == 2
    assert report.total_failed == 0


def test_custom_output_flag_used(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    archive_path = game_root / "game" / "archive.rpa"
    build_archive(archive_path, {"a.txt": b"hi"}, version="RPA-3.0")
    archives = find_archives(game_root)
    custom = tmp_path / "custom_out"

    report = extract_rpa.extract(
        game_root=game_root, game_dir=game_root / "game", output=str(custom), archives=archives
    )
    assert (custom / "a.txt").read_bytes() == b"hi"


def test_in_place_extraction_writes_into_game_dir(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    archive_path = game_root / "game" / "archive.rpa"
    build_archive(archive_path, {"a.txt": b"hi"}, version="RPA-3.0")
    archives = find_archives(game_root)

    report = extract_rpa.extract(
        game_root=game_root, game_dir=game_root / "game", in_place=True, archives=archives
    )
    assert (game_root / "game" / "a.txt").read_bytes() == b"hi"
    assert report.in_place is True


def test_overwrite_protection_without_force(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    archive_path = game_root / "game" / "archive.rpa"
    build_archive(archive_path, {"a.txt": b"new content"}, version="RPA-3.0")
    archives = find_archives(game_root)

    out_dir = game_root / "unren-extracted"
    out_dir.mkdir()
    (out_dir / "a.txt").write_text("existing content")

    report = extract_rpa.extract(game_root=game_root, game_dir=game_root / "game", archives=archives)
    assert report.total_failed == 1
    assert "already exist" in report.archives[0].skipped_reason
    # Original destination content must be untouched.
    assert (out_dir / "a.txt").read_text() == "existing content"


def test_force_overwrites_and_backs_up(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    archive_path = game_root / "game" / "archive.rpa"
    build_archive(archive_path, {"a.txt": b"new content"}, version="RPA-3.0")
    archives = find_archives(game_root)

    out_dir = game_root / "unren-extracted"
    out_dir.mkdir()
    (out_dir / "a.txt").write_text("existing content")

    report = extract_rpa.extract(
        game_root=game_root, game_dir=game_root / "game", force=True, archives=archives
    )
    assert report.total_extracted_files == 1
    assert (out_dir / "a.txt").read_bytes() == b"new content"
    backup = game_root / ".unren" / "backups" / "unren-extracted" / "a.txt"
    assert backup.read_text() == "existing content"


def test_original_rpa_never_overwritten_or_modified(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    archive_path = game_root / "game" / "archive.rpa"
    build_archive(archive_path, {"a.txt": b"hello"}, version="RPA-3.0")
    original_bytes = archive_path.read_bytes()
    archives = find_archives(game_root)

    extract_rpa.extract(game_root=game_root, game_dir=game_root / "game", in_place=True, archives=archives)
    assert archive_path.read_bytes() == original_bytes


def test_output_path_exists_as_file_raises(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    conflicting = game_root / "unren-extracted"
    conflicting.write_text("i am a file, not a dir")
    archive_path = game_root / "game" / "archive.rpa"
    build_archive(archive_path, {"a.txt": b"hi"}, version="RPA-3.0")
    archives = find_archives(game_root)

    with pytest.raises(OutputPathError):
        extract_rpa.extract(game_root=game_root, game_dir=game_root / "game", archives=archives)


def test_unsupported_format_archive_skipped_others_still_processed(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    good = game_root / "game" / "good.rpa"
    build_archive(good, {"a.txt": b"hi"}, version="RPA-3.0")
    bad = game_root / "game" / "bad.rpa"
    bad.write_bytes(b"RPAN3.0" + b"\x00" * 20)

    archives = [
        ArchiveInfo(path=good, extension=".rpa", format="RPA-3.0"),
        ArchiveInfo(path=bad, extension=".rpa", format="RPAN-3.0"),
    ]
    report = extract_rpa.extract(game_root=game_root, game_dir=game_root / "game", archives=archives)
    assert report.total_archives == 2
    assert report.total_failed == 1
    assert report.total_extracted_files == 1
    good_plan = next(p for p in report.archives if p.archive == str(good))
    bad_plan = next(p for p in report.archives if p.archive == str(bad))
    assert good_plan.ok
    assert not bad_plan.ok


def test_multiple_archives_all_extracted(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    a1 = game_root / "game" / "one.rpa"
    a2 = game_root / "game" / "two.rpa"
    build_archive(a1, {"one.txt": b"1"}, version="RPA-2.0")
    build_archive(a2, {"two.txt": b"2"}, version="RPA-3.0")
    archives = find_archives(game_root)

    report = extract_rpa.extract(game_root=game_root, game_dir=game_root / "game", archives=archives)
    assert report.total_archives == 2
    assert report.total_extracted_files == 2
    out_dir = game_root / "unren-extracted"
    assert (out_dir / "one.txt").read_bytes() == b"1"
    assert (out_dir / "two.txt").read_bytes() == b"2"
