"""Unit tests for unren.actions.enable_console / enable_devmode."""

from __future__ import annotations

from pathlib import Path

import pytest

from unren.actions import enable_console, enable_devmode
from unren.core.errors import MissingGameDirectoryError


def test_console_enable_writes_marker(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    report = enable_console.enable(game_dir=game_dir)
    assert report.applied is True
    assert report.already_enabled is False
    content = (game_dir / "unren-console.rpy").read_text()
    assert "config.console = True" in content
    assert "config.developer = True" in content


def test_console_enable_idempotent(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    enable_console.enable(game_dir=game_dir)
    report2 = enable_console.enable(game_dir=game_dir)
    assert report2.already_enabled is True
    assert report2.applied is False


def test_console_enable_missing_game_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(MissingGameDirectoryError):
        enable_console.enable(game_dir=tmp_path / "does_not_exist")


def test_console_enable_dry_run_no_write(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    report = enable_console.enable(game_dir=game_dir, dry_run=True)
    assert report.applied is False
    assert not (game_dir / "unren-console.rpy").exists()


def test_devmode_enable_writes_marker(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    report = enable_devmode.enable(game_dir=game_dir)
    assert report.applied is True
    content = (game_dir / "unren-debug.rpy").read_text()
    assert "config.debug = True" in content


def test_devmode_enable_idempotent(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    enable_devmode.enable(game_dir=game_dir)
    report2 = enable_devmode.enable(game_dir=game_dir)
    assert report2.already_enabled is True


def test_devmode_enable_missing_game_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(MissingGameDirectoryError):
        enable_devmode.enable(game_dir=tmp_path / "does_not_exist")


def test_console_and_devmode_are_independent_files(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    enable_console.enable(game_dir=game_dir)
    enable_devmode.enable(game_dir=game_dir)
    assert (game_dir / "unren-console.rpy").is_file()
    assert (game_dir / "unren-debug.rpy").is_file()
