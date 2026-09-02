"""Unit tests for unren.core.paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from unren.core.errors import PathNotFoundError
from unren.core.paths import find_upwards, iter_files_shallow, resolve_existing_dir


def test_resolve_existing_dir_success(tmp_path: Path) -> None:
    d = tmp_path / "subdir"
    d.mkdir()
    resolved = resolve_existing_dir(str(d))
    assert resolved == d.resolve()
    assert resolved.is_absolute()


def test_resolve_existing_dir_expands_user(monkeypatch, tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    resolved = resolve_existing_dir("~")
    assert resolved == fake_home.resolve()


def test_resolve_existing_dir_missing_path_raises(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"
    with pytest.raises(PathNotFoundError):
        resolve_existing_dir(missing)


def test_resolve_existing_dir_file_not_dir_raises(tmp_path: Path) -> None:
    f = tmp_path / "afile.txt"
    f.write_text("hi", encoding="utf-8")
    with pytest.raises(PathNotFoundError):
        resolve_existing_dir(f)


def test_find_upwards_finds_marker_in_start(tmp_path: Path) -> None:
    d = tmp_path / "root"
    (d / "game").mkdir(parents=True)
    found = find_upwards(d, markers=("game", "renpy"))
    assert found == d


def test_find_upwards_finds_marker_in_ancestor(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "game").mkdir(parents=True)
    nested = root / "a" / "b" / "c"
    nested.mkdir(parents=True)
    found = find_upwards(nested, markers=("game", "renpy"))
    assert found == root


def test_find_upwards_respects_max_levels(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "game").mkdir(parents=True)
    # 8 levels deep, but max_levels default search radius (6) shouldn't reach the marker.
    nested = root
    for i in range(8):
        nested = nested / f"lvl{i}"
    nested.mkdir(parents=True)
    found = find_upwards(nested, markers=("game",), max_levels=2)
    assert found is None


def test_find_upwards_returns_none_when_absent(tmp_path: Path) -> None:
    d = tmp_path / "no_markers_anywhere"
    d.mkdir()
    found = find_upwards(d, markers=("game", "renpy"))
    assert found is None


def test_iter_files_shallow_yields_files_within_depth(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("1", encoding="utf-8")
    nested = tmp_path / "sub" / "deep"
    nested.mkdir(parents=True)
    (nested / "b.txt").write_text("2", encoding="utf-8")

    files = set(iter_files_shallow(tmp_path, max_depth=3))
    assert (tmp_path / "a.txt") in files
    assert (nested / "b.txt") in files


def test_iter_files_shallow_nonexistent_dir_yields_nothing(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    assert list(iter_files_shallow(missing)) == []
