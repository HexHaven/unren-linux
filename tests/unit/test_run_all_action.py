"""Unit tests for unren.actions.run_all (`unren all` orchestration)."""

from __future__ import annotations

from pathlib import Path

from unren.actions import run_all
from unren.core.context import GameContext, PythonRuntime, RenPyVersionInfo
from unren.detection.renpy import RenPyGeneration


def _make_ctx(root: Path, *, game_dir: Path | None, generation: RenPyGeneration) -> GameContext:
    return GameContext(
        root=root,
        game_dir=game_dir,
        renpy_dir=None,
        runtime=PythonRuntime(executable=None, version=None, source="unknown"),
        renpy_version=RenPyVersionInfo(generation=generation, major=None, method=None),
        archives=[],
    )


def test_all_runs_patch_stages_when_no_archives_or_rpyc(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    ctx = _make_ctx(tmp_path, game_dir=game_dir, generation=RenPyGeneration.CURRENT)

    report = run_all.run_all(ctx=ctx, dry_run=False)

    stage_names = [s.stage for s in report.stages]
    assert stage_names == list(run_all.STAGES)
    # extract: no archives -> ok (nothing to do isn't a failure)
    extract_stage = next(s for s in report.stages if s.stage == "extract")
    assert extract_stage.ok is True
    # decompile: no rpyc files -> ok
    decompile_stage = next(s for s in report.stages if s.stage == "decompile")
    assert decompile_stage.ok is True
    # patch stages applied
    console_stage = next(s for s in report.stages if s.stage == "console_enable")
    assert console_stage.ok is True
    assert (game_dir / "unren-console.rpy").is_file()
    assert (game_dir / "unren-debug.rpy").is_file()
    assert (game_dir / "unren-skip.rpy").is_file()
    assert (game_dir / "unren-rollback.rpy").is_file()
    assert (game_dir / "unren-quicksave.rpy").is_file()
    assert (game_dir / "unren-qmenu.rpy").is_file()
    assert (game_dir / "unren-nsync.rpy").is_file()
    assert report.total_failed == 0


def test_all_skips_decompile_on_unknown_generation(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    ctx = _make_ctx(tmp_path, game_dir=game_dir, generation=RenPyGeneration.UNKNOWN)

    report = run_all.run_all(ctx=ctx, dry_run=False)

    decompile_stage = next(s for s in report.stages if s.stage == "decompile")
    assert decompile_stage.skipped is True
    assert decompile_stage.ok is False
    assert "unknown" in decompile_stage.reason.lower()
    # decompile being skipped must not abort later stages (fail-closed, not
    # fail-abort): patch stages still run.
    console_stage = next(s for s in report.stages if s.stage == "console_enable")
    assert console_stage.ok is True


def test_all_skips_patch_stages_when_no_game_dir(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, game_dir=None, generation=RenPyGeneration.CURRENT)

    report = run_all.run_all(ctx=ctx, dry_run=False)

    for stage_name in run_all.STAGES[2:]:
        stage = next(s for s in report.stages if s.stage == stage_name)
        assert stage.skipped is True
        assert stage.ok is False


def test_all_dry_run_writes_nothing(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    ctx = _make_ctx(tmp_path, game_dir=game_dir, generation=RenPyGeneration.CURRENT)

    run_all.run_all(ctx=ctx, dry_run=True)

    assert not (game_dir / "unren-console.rpy").exists()
    assert not (game_dir / "unren-debug.rpy").exists()
    assert not (game_dir / "unren-skip.rpy").exists()


def test_all_idempotent_second_run(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    ctx = _make_ctx(tmp_path, game_dir=game_dir, generation=RenPyGeneration.CURRENT)

    run_all.run_all(ctx=ctx, dry_run=False)
    report2 = run_all.run_all(ctx=ctx, dry_run=False)

    assert report2.total_failed == 0
    console_stage = next(s for s in report2.stages if s.stage == "console_enable")
    assert console_stage.detail.patch.already_present is True
