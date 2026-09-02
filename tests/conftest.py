"""Shared pytest fixtures: paths to the synthetic Ren'Py fixture directories."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def renpy6_game(fixtures_dir: Path) -> Path:
    return fixtures_dir / "renpy6_game"


@pytest.fixture
def renpy7_game(fixtures_dir: Path) -> Path:
    return fixtures_dir / "renpy7_game"


@pytest.fixture
def renpy8_game(fixtures_dir: Path) -> Path:
    return fixtures_dir / "renpy8_game"


@pytest.fixture
def non_game_dir(tmp_path: Path) -> Path:
    """A plain directory with no Ren'Py markers at all."""
    d = tmp_path / "not_a_game"
    d.mkdir()
    (d / "readme.txt").write_text("just some random directory\n", encoding="utf-8")
    return d
