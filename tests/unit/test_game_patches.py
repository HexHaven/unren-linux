"""Unit tests for unren.actions.game_patches (skip/skipall/rollback/quicksave/quickmenu/nosync)."""

from __future__ import annotations

from pathlib import Path

import pytest

from unren.actions import game_patches
from unren.core.errors import MissingGameDirectoryError

ALL_ACTIONS = (
    (game_patches.enable_skip, "unren-skip.rpy", "allow_skipping"),
    (game_patches.enable_skip_all, "unren-skipall.rpy", "_preferences.transitions"),
    (game_patches.enable_rollback, "unren-rollback.rpy", "rollback_enabled"),
    (game_patches.enable_quicksave, "unren-quicksave.rpy", "QuickSave"),
    (game_patches.enable_quickmenu, "unren-qmenu.rpy", "quick_menu"),
    (game_patches.disable_save_sync, "unren-nsync.rpy", "has_sync"),
)


@pytest.mark.parametrize("fn,filename,expected_substring", ALL_ACTIONS)
def test_writes_expected_marker_file(tmp_path: Path, fn, filename: str, expected_substring: str) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    result = fn(game_dir=game_dir)
    assert result.applied is True
    target = game_dir / filename
    assert target.is_file()
    assert expected_substring in target.read_text()


@pytest.mark.parametrize("fn,filename,expected_substring", ALL_ACTIONS)
def test_idempotent(tmp_path: Path, fn, filename: str, expected_substring: str) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    fn(game_dir=game_dir)
    result2 = fn(game_dir=game_dir)
    assert result2.already_present is True
    assert result2.applied is False


@pytest.mark.parametrize("fn,filename,expected_substring", ALL_ACTIONS)
def test_missing_game_dir_raises(tmp_path: Path, fn, filename: str, expected_substring: str) -> None:
    with pytest.raises(MissingGameDirectoryError):
        fn(game_dir=tmp_path / "does_not_exist")


@pytest.mark.parametrize("fn,filename,expected_substring", ALL_ACTIONS)
def test_dry_run_does_not_write(tmp_path: Path, fn, filename: str, expected_substring: str) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    result = fn(game_dir=game_dir, dry_run=True)
    assert result.applied is False
    assert not (game_dir / filename).exists()


def test_skip_and_skipall_are_independent_files(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    game_patches.enable_skip(game_dir=game_dir)
    game_patches.enable_skip_all(game_dir=game_dir)
    assert (game_dir / "unren-skip.rpy").is_file()
    assert (game_dir / "unren-skipall.rpy").is_file()
