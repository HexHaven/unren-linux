"""Unit tests for unren.detection.game (game-root discovery + GameContext assembly)."""

from __future__ import annotations

from pathlib import Path

import pytest

from unren.core.errors import NotAGameDirectoryError, PathNotFoundError
from unren.detection.game import detect_game, require_game


def test_detect_game_true_for_renpy_fixtures(renpy6_game: Path, renpy8_game: Path) -> None:
    ctx6 = detect_game(renpy6_game)
    assert ctx6.is_game is True
    assert ctx6.game_dir is not None

    ctx8 = detect_game(renpy8_game)
    assert ctx8.is_game is True


def test_detect_game_false_for_plain_dir(non_game_dir: Path) -> None:
    ctx = detect_game(non_game_dir)
    assert ctx.is_game is False
    assert ctx.game_dir is None
    assert ctx.renpy_dir is None


def test_detect_game_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(PathNotFoundError):
        detect_game(tmp_path / "nope")


def test_detect_game_finds_root_from_nested_start(renpy8_game: Path) -> None:
    nested = renpy8_game / "game"
    ctx = detect_game(nested)
    assert ctx.root == renpy8_game.resolve()


def test_require_game_raises_when_not_a_game(non_game_dir: Path) -> None:
    with pytest.raises(NotAGameDirectoryError):
        require_game(non_game_dir)


def test_require_game_returns_context_when_game(renpy7_game: Path) -> None:
    ctx = require_game(renpy7_game)
    assert ctx.is_game is True
    assert ctx.renpy_version.major == 7
