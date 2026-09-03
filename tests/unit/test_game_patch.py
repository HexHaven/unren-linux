"""Unit tests for unren.core.game_patch (shared idempotent .rpy patch writer)."""

from __future__ import annotations

from pathlib import Path

from unren.core.game_patch import apply_patch_file


def test_writes_file_when_absent(tmp_path: Path) -> None:
    result = apply_patch_file(game_dir=tmp_path, filename="unren-test.rpy", content="hello")
    assert result.applied is True
    assert result.already_present is False
    target = tmp_path / "unren-test.rpy"
    assert target.read_text() == "hello\n"


def test_appends_trailing_newline_if_missing(tmp_path: Path) -> None:
    apply_patch_file(game_dir=tmp_path, filename="unren-test.rpy", content="no newline")
    assert (tmp_path / "unren-test.rpy").read_text().endswith("\n")


def test_idempotent_second_call_is_noop(tmp_path: Path) -> None:
    apply_patch_file(game_dir=tmp_path, filename="unren-test.rpy", content="v1")
    result = apply_patch_file(game_dir=tmp_path, filename="unren-test.rpy", content="v2 - should be ignored")
    assert result.already_present is True
    assert result.applied is False
    # content on disk must be untouched (v1), not overwritten with v2
    assert (tmp_path / "unren-test.rpy").read_text() == "v1\n"


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    result = apply_patch_file(game_dir=tmp_path, filename="unren-test.rpy", content="hello", dry_run=True)
    assert result.dry_run is True
    assert result.applied is False
    assert not (tmp_path / "unren-test.rpy").exists()


def test_dry_run_reports_already_present(tmp_path: Path) -> None:
    apply_patch_file(game_dir=tmp_path, filename="unren-test.rpy", content="v1")
    result = apply_patch_file(game_dir=tmp_path, filename="unren-test.rpy", content="v1", dry_run=True)
    assert result.already_present is True
    assert result.applied is False


def test_creates_game_dir_if_missing(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    assert not game_dir.exists()
    apply_patch_file(game_dir=game_dir, filename="unren-test.rpy", content="hello")
    assert (game_dir / "unren-test.rpy").is_file()
