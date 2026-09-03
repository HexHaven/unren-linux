"""Unit tests for unren.actions.cleanup (restore_backups / delete_backups)."""

from __future__ import annotations

from pathlib import Path

import pytest

from unren.actions import cleanup
from unren.core.errors import ConfirmationRequiredError


def _seed_backup(game_root: Path, rel: str, content: str) -> Path:
    backup_path = game_root / ".unren" / "backups" / rel
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_text(content)
    return backup_path


def test_restore_no_backups_is_empty_not_error(tmp_path: Path) -> None:
    report = cleanup.restore_backups(game_root=tmp_path)
    assert report.total_files == 0
    assert report.total_failed == 0


def test_restore_moves_backup_over_target(tmp_path: Path) -> None:
    target = tmp_path / "game" / "a.rpy"
    target.parent.mkdir(parents=True)
    target.write_text("current (bad) content")
    _seed_backup(tmp_path, "game/a.rpy", "original content")

    report = cleanup.restore_backups(game_root=tmp_path)
    assert report.total_succeeded == 1
    assert target.read_text() == "original content"
    # backup itself is consumed (moved, not copied)
    assert not (tmp_path / ".unren" / "backups" / "game" / "a.rpy").exists()


def test_restore_dry_run_makes_no_changes(tmp_path: Path) -> None:
    target = tmp_path / "game" / "a.rpy"
    target.parent.mkdir(parents=True)
    target.write_text("current content")
    backup = _seed_backup(tmp_path, "game/a.rpy", "original content")

    report = cleanup.restore_backups(game_root=tmp_path, dry_run=True)
    assert report.total_files == 1
    assert target.read_text() == "current content"
    assert backup.exists()


def test_restore_recreates_target_if_missing(tmp_path: Path) -> None:
    _seed_backup(tmp_path, "game/newly_missing.rpy", "restored content")
    report = cleanup.restore_backups(game_root=tmp_path)
    assert report.total_succeeded == 1
    assert (tmp_path / "game" / "newly_missing.rpy").read_text() == "restored content"


def test_delete_requires_confirmation(tmp_path: Path) -> None:
    _seed_backup(tmp_path, "game/a.rpy", "x")
    with pytest.raises(ConfirmationRequiredError):
        cleanup.delete_backups(game_root=tmp_path)


def test_delete_dry_run_does_not_require_confirmation(tmp_path: Path) -> None:
    backup = _seed_backup(tmp_path, "game/a.rpy", "x")
    report = cleanup.delete_backups(game_root=tmp_path, dry_run=True)
    assert report.total_files == 1
    assert backup.exists()  # dry-run never deletes


def test_delete_with_confirm_removes_files(tmp_path: Path) -> None:
    backup = _seed_backup(tmp_path, "game/a.rpy", "x")
    report = cleanup.delete_backups(game_root=tmp_path, confirm=True)
    assert report.total_succeeded == 1
    assert not backup.exists()


def test_delete_no_backups_is_empty_not_error(tmp_path: Path) -> None:
    report = cleanup.delete_backups(game_root=tmp_path, confirm=True)
    assert report.total_files == 0
    assert report.total_failed == 0


def test_restore_multiple_files(tmp_path: Path) -> None:
    _seed_backup(tmp_path, "game/a.rpy", "a-content")
    _seed_backup(tmp_path, "game/sub/b.rpy", "b-content")
    report = cleanup.restore_backups(game_root=tmp_path)
    assert report.total_succeeded == 2
    assert (tmp_path / "game" / "a.rpy").read_text() == "a-content"
    assert (tmp_path / "game" / "sub" / "b.rpy").read_text() == "b-content"
