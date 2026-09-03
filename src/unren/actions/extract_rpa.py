"""`unren extract` action: discover and extract RPA archives (Milestone 2).

Scope (per task card): only the *extraction* concern. Archive discovery
(finding `.rpa`-like files, classifying their header) already exists in
`unren.detection.archives` (Milestone 1) and is reused as-is here.

Output management:
    - default: a sibling `unren-extracted/` folder next to the detected game
      root (never inside `game/` itself, so nothing is accidentally picked up
      by the game engine).
    - `--output PATH`: extract into PATH instead.
    - `--in-place`: extract into the game directory itself (or the game root
      if no `game/` subdir), matching upstream's behavior of unpacking
      alongside the original files. Must be requested explicitly - never the
      default, since it mutates the game tree itself.

Safety:
    - `--dry-run` (global flag): compute and report the full plan (per-archive
      format, per-member destination paths, byte counts) without writing or
      creating anything.
    - Overwrite protection: if any computed destination file already exists,
      that archive's extraction is refused with `OverwriteProtectionError`
      unless `--force` is given. This never touches the original `.rpa`
      archive itself - only ever the extracted member files.
    - `--force` additionally backs up any destination file about to be
      overwritten into `<game_root>/.unren/backups/...` (see
      `unren.core.backup`) before writing over it.

Unsupported archive formats (anything `unren.adapters.rpatool` doesn't
understand the container layout of - e.g. RPAN-3.0/ZiX/SVAC/RWA "neutron"
archives) are reported as a per-archive error and skipped; they do not abort
extraction of the other, supported archives in the same run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from unren.adapters import rpatool
from unren.core.backup import backup_file
from unren.core.errors import OutputPathError, OverwriteProtectionError, UnrenError
from unren.detection.archives import ArchiveInfo, find_archives


@dataclass
class MemberPlan:
    member: str
    destination: str
    size: int
    exists: bool


@dataclass
class ArchivePlan:
    archive: str
    format: str
    output_dir: str
    members: list[MemberPlan] = field(default_factory=list)
    extracted: int = 0
    skipped_reason: str | None = None
    conflicts: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.skipped_reason is None


@dataclass
class ExtractionReport:
    game_root: str
    output_root: str
    dry_run: bool
    in_place: bool
    archives: list[ArchivePlan] = field(default_factory=list)

    @property
    def total_archives(self) -> int:
        return len(self.archives)

    @property
    def total_extracted_files(self) -> int:
        return sum(a.extracted for a in self.archives)

    @property
    def total_failed(self) -> int:
        return sum(1 for a in self.archives if not a.ok)


def _default_output_dir(game_root: Path) -> Path:
    return game_root / "unren-extracted"


def _in_place_output_dir(game_root: Path, game_dir: Path | None) -> Path:
    return game_dir if game_dir is not None else game_root


def resolve_output_root(
    *, game_root: Path, game_dir: Path | None, output: str | None, in_place: bool
) -> Path:
    if in_place and output:
        raise OutputPathError(
            "--output and --in-place are mutually exclusive.",
            details={"output": output},
        )
    if in_place:
        return _in_place_output_dir(game_root, game_dir)
    if output:
        return Path(output).expanduser()
    return _default_output_dir(game_root)


def _validate_output_dir(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise OutputPathError(
            f"Output path exists and is not a directory: {path}",
            details={"path": str(path)},
        )


def _plan_archive(archive: ArchiveInfo, *, output_dir: Path) -> ArchivePlan:
    plan = ArchivePlan(archive=str(archive.path), format=archive.format, output_dir=str(output_dir))

    if archive.format not in rpatool.SUPPORTED_FORMATS:
        plan.skipped_reason = (
            f"format '{archive.format}' is not supported for extraction "
            "(only RPA-1.0/2.0/3.0/3.2 container layouts are implemented)"
        )
        return plan

    try:
        reader = rpatool.open_archive(archive.path)
    except UnrenError as exc:
        plan.skipped_reason = exc.message
        return plan

    for name in reader.list_names():
        entry = reader.entries[name]
        dest = output_dir / Path(name)
        plan.members.append(
            MemberPlan(member=name, destination=str(dest), size=entry.length, exists=dest.exists())
        )
    plan.conflicts = [m.destination for m in plan.members if m.exists]
    return plan


def build_plan(
    *,
    game_root: Path,
    game_dir: Path | None,
    output: str | None,
    in_place: bool,
    archives: list[ArchiveInfo] | None = None,
) -> ExtractionReport:
    """Compute (without mutating anything) the full extraction plan."""
    output_root = resolve_output_root(
        game_root=game_root, game_dir=game_dir, output=output, in_place=in_place
    )
    _validate_output_dir(output_root)

    found = archives if archives is not None else find_archives(game_root)
    report = ExtractionReport(
        game_root=str(game_root),
        output_root=str(output_root),
        dry_run=True,
        in_place=in_place,
    )
    for archive in found:
        report.archives.append(_plan_archive(archive, output_dir=output_root))
    return report


def _write_member(reader: rpatool.RpaArchiveReader, member: MemberPlan, *, force: bool, game_root: Path) -> None:
    dest = Path(member.destination)
    if dest.exists() and force:
        backup_file(game_root, dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = reader.read(member.member)
    dest.write_bytes(data)


def execute_plan(report: ExtractionReport, *, force: bool = False) -> ExtractionReport:
    """Mutate the filesystem according to a previously computed plan.

    Per-archive: if there are unresolved conflicts (existing destination
    files) and `force` is False, the archive is skipped with an
    OverwriteProtectionError message rather than partially extracted.
    """
    game_root = Path(report.game_root)
    for plan in report.archives:
        if not plan.ok:
            continue
        if plan.conflicts and not force:
            plan.skipped_reason = (
                OverwriteProtectionError(
                    f"{len(plan.conflicts)} destination file(s) already exist; "
                    "re-run with --force to overwrite (existing files are backed up first).",
                    details={"conflicts": plan.conflicts[:20]},
                ).message
            )
            continue
        try:
            reader = rpatool.open_archive(Path(plan.archive))
            for member in plan.members:
                _write_member(reader, member, force=force, game_root=game_root)
                plan.extracted += 1
        except UnrenError as exc:
            plan.skipped_reason = exc.message
    report.dry_run = False
    return report


def extract(
    *,
    game_root: Path,
    game_dir: Path | None,
    output: str | None = None,
    in_place: bool = False,
    dry_run: bool = False,
    force: bool = False,
    archives: list[ArchiveInfo] | None = None,
) -> ExtractionReport:
    """High-level entry point used by the CLI: plan, then execute unless dry_run."""
    report = build_plan(
        game_root=game_root, game_dir=game_dir, output=output, in_place=in_place, archives=archives
    )
    if dry_run:
        return report
    return execute_plan(report, force=force)
