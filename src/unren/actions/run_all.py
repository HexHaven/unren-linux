"""`unren all` command: run every relevant non-destructive action sequentially.

Upstream: `ACT.5`/`ACT.6` combo menu options ("Run all common operations")
bundle several individual actions into one convenience invocation
(docs/UPSTREAM-BEHAVIOR.md; Proposed-Bauplan.md §7 lists `unren all` as a
first-class CLI command). This module is the Linux equivalent: it runs, in a
fixed and safety-ordered sequence, every implemented action that is
non-destructive and safe to always apply:

    1. detect          (read-only; establishes generation/context - if this
                         fails or the game is unrecognized, nothing else runs)
    2. extract          (RPA archives -> game/ tree; must precede decompile,
                         since some games ship .rpyc only inside archives)
    3. decompile        (.rpyc/.rpymc -> .rpy; requires the Ren'Py generation
                         resolved by step 1)
    4. console enable
    5. devmode enable
    6. skip enable
    7. rollback enable
    8. quicksave enable
    9. quickmenu enable
   10. disable_save_sync

Order matches the task card's explicit safety requirement ("Detection ->
RPA -> RPYC -> Console/Devmode -> Cleanup"); the additive `.rpy` game-config
patches (6-10) are appended after console/devmode since they're the same
zero-risk idempotent-file-write mechanism and share no ordering constraint
with anything else.

Deliberately excluded from `all`: `cleanup restore`/`cleanup delete`. Both
operate on backups created by *other* runs and are either a destructive undo
or an irreversible delete - neither belongs in an "apply everything" bulk
convenience command. They remain separate, explicitly-invoked subcommands.

Fail-closed / no silent skip: every stage's outcome (ok, skipped, or failed)
is recorded in the returned report, even when an earlier stage fails - a
failure in one stage does not silently abort or hide the status of later
stages; it does, however, prevent stages that structurally depend on it
(e.g. decompile needs a resolved generation) from running, and that
dependency-skip is itself recorded with an explicit reason rather than
omitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from unren.actions import decompile_rpyc, enable_console, enable_devmode, extract_rpa, game_patches
from unren.core.errors import UnrenError
from unren.detection.archives import ArchiveInfo
from unren.detection.game import GameContext
from unren.detection.renpy import RenPyGeneration
from unren.detection.rpyc import find_rpyc_files

STAGES = (
    "extract",
    "decompile",
    "console_enable",
    "devmode_enable",
    "skip_enable",
    "rollback_enable",
    "quicksave_enable",
    "quickmenu_enable",
    "disable_save_sync",
)


@dataclass
class StageResult:
    stage: str
    ok: bool
    skipped: bool = False
    reason: str | None = None
    detail: Any = None


@dataclass
class AllReport:
    game_root: str
    dry_run: bool
    stages: list[StageResult] = field(default_factory=list)

    @property
    def total_failed(self) -> int:
        return sum(1 for s in self.stages if not s.ok and not s.skipped)

    @property
    def total_ok(self) -> int:
        return sum(1 for s in self.stages if s.ok)


def run_all(*, ctx: GameContext, dry_run: bool = False, force: bool = False) -> AllReport:
    """Run every relevant non-destructive action against an already-detected game.

    `ctx` must come from `unren.detection.game.detect_game()` (the CLI layer
    resolves detection first, same as every other action command, so a
    detection failure is reported once at the CLI boundary, not duplicated
    here).
    """
    report = AllReport(game_root=str(ctx.root), dry_run=dry_run)

    # --- extract ---------------------------------------------------------
    try:
        extract_report = extract_rpa.extract(
            game_root=ctx.root,
            game_dir=ctx.game_dir,
            dry_run=dry_run,
            force=force,
            archives=[
                ArchiveInfo(path=a.path, extension=a.extension, format=a.format) for a in ctx.archives
            ],
        )
        ok = extract_report.total_archives == 0 or extract_report.total_failed < extract_report.total_archives
        report.stages.append(StageResult(stage="extract", ok=ok, detail=extract_report))
    except UnrenError as exc:
        report.stages.append(StageResult(stage="extract", ok=False, reason=exc.message))

    # --- decompile ---------------------------------------------------------
    if ctx.renpy_version.generation is RenPyGeneration.UNKNOWN:
        report.stages.append(
            StageResult(
                stage="decompile",
                ok=False,
                skipped=True,
                reason="Ren'Py generation is unknown; refusing to guess a decompiler variant.",
            )
        )
    else:
        try:
            decompile_report = decompile_rpyc.decompile(
                game_root=ctx.root,
                game_dir=ctx.game_dir,
                generation=ctx.renpy_version.generation,
                dry_run=dry_run,
                force=force,
                rpyc_files=find_rpyc_files(ctx.game_dir or ctx.root),
            )
            ok = (
                decompile_report.total_files == 0
                or decompile_report.total_failed < decompile_report.total_files
            )
            report.stages.append(StageResult(stage="decompile", ok=ok, detail=decompile_report))
        except UnrenError as exc:
            report.stages.append(StageResult(stage="decompile", ok=False, reason=exc.message))

    # --- game/-dir-scoped additive patches ---------------------------------
    if ctx.game_dir is None:
        for stage in STAGES[2:]:
            report.stages.append(
                StageResult(
                    stage=stage,
                    ok=False,
                    skipped=True,
                    reason="No game/ directory found to patch.",
                )
            )
        return report

    game_dir: Path = ctx.game_dir

    def _patch_stage(stage: str, fn, **kwargs) -> None:
        try:
            result = fn(game_dir=game_dir, dry_run=dry_run, **kwargs)
            report.stages.append(StageResult(stage=stage, ok=True, detail=result))
        except UnrenError as exc:
            report.stages.append(StageResult(stage=stage, ok=False, reason=exc.message))

    _patch_stage("console_enable", lambda **kw: enable_console.enable(**kw))
    _patch_stage("devmode_enable", lambda **kw: enable_devmode.enable(**kw))
    _patch_stage("skip_enable", game_patches.enable_skip)
    _patch_stage("rollback_enable", game_patches.enable_rollback)
    _patch_stage("quicksave_enable", game_patches.enable_quicksave)
    _patch_stage("quickmenu_enable", game_patches.enable_quickmenu)
    _patch_stage("disable_save_sync", game_patches.disable_save_sync)

    return report
