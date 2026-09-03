"""`unren decompile` action: discover and decompile .rpyc/.rpymc files (Milestone 3).

Scope (per task card): decompilation only. RPYC discovery/format sniffing
lives in `unren.detection.rpyc` (Milestone 3, this module reuses it as-is,
mirroring how Milestone 2's extract_rpa reuses Milestone 1's
`unren.detection.archives`). Ren'Py generation detection is Milestone 1's
`unren.detection.renpy`.

Generation-specific decompilation
----------------------------------
Per docs/UPSTREAM-BEHAVIOR.md §7.7 ("RESOLVED" open question): upstream's own
`RPATOOL_NEW`/`UNRPYC_NEW` variant-selection gate is driven by the *game's
bundled Python major version*, not directly by the detected Ren'Py major
version - the two are correlated but not identical (a Ren'Py-8 game could in
principle still ship a Python-2 bundled runtime; older Ren'Py-7 games
occasionally bundle Python 3). This port follows that same principle:

    1. If the game's Ren'Py generation is CURRENT (>=8): only the vendored
       "current" unrpyc (v2.0.3, Python 3.9+-only) is even a candidate - it's
       the only variant that understands Ren'Py 8-era AST shapes. Requires a
       resolved Python >=3.9 runtime (system preferred, else Ren'Py-bundled);
       unresolved -> fail closed (RuntimeResolutionError), never silently
       fall back to "legacy".
    2. If the game's Ren'Py generation is LEGACY (<=7): prefer the vendored
       "legacy" unrpyc (v1.3.2, real Python 2 source) via a resolved Python 2
       runtime (system or Ren'Py-bundled - see `unren.detection.python`).
       Python 2 is frequently *unavailable* on modern systems (a documented
       known risk on this milestone's task card). When no Python 2 runtime
       resolves, this module falls back to the vendored "current" unrpyc
       (Python 3.9+) against the same files: it was verified (Milestone 3
       vendoring pass) to successfully decompile real Ren'Py 7-era ("RENPY
       RPC2") files, emitting only an informational compatibility warning
       from unrpyc itself, not a hard failure. This fallback exists purely
       for the "Python 2 may not exist on this system" risk documented on
       the task card; it never silently swallows a *format* it cannot
       recognize (see the RPC1/UNKNOWN handling below) - the same "current"
       binary path already contains upstream's own is_rpyc_v1 branch, so
       Ren'Py 6 RPC1-format files are attempted through it too, when that's
       the only runtime available.
    3. If the game's Ren'Py generation is UNKNOWN, this module refuses the
       whole operation with a clear error rather than guessing a variant
       (fail-closed - matches the task card's Ren'Py-detection-cascade
       philosophy already established in Milestone 1).

Independently of generation-level variant selection, every discovered file is
also sniffed at the *container format* level (`unren.detection.rpyc`,
RPC1/RPC2/UNKNOWN). A file whose header does not match either known RPYC
container shape is never handed to unrpyc and never silently dropped from the
report - it is recorded as a per-file error (fail-closed, per the task card's
explicit "unbekannte RPYC-Variante -> Error, nicht Silent Skip" acceptance
criterion).

Output management (mirrors extract_rpa's shape):
    - default: files are first copied into a sibling `unren-decompiled/`
      folder (never into `game/` itself), preserving their relative path,
      and unrpyc is run against those *copies* - so the original `.rpyc`
      tree is never touched and the produced `.rpy` files land next to their
      copied `.rpyc` siblings inside the output folder. This indirection is
      necessary because upstream unrpyc always writes its output next to its
      input; a separate non-destructive output location is Milestone 3's own
      requirement (task card: "Output management (analog RPA: separate
      Output-Ordner)"), not something equivalent to run "into" for unrpyc.
    - `--output PATH`: use PATH as that staging/output root instead.
    - `--in-place`: skip staging; run unrpyc directly against the original
      `.rpyc` files, so `.rpy` output lands next to them inside `game/`
      (matches unrpyc's native/upstream default behavior exactly). Must be
      requested explicitly, never the default.

Safety:
    - `--dry-run` (global flag): compute and report the full plan (per-file
      format, selected variant, destination `.rpy` path, conflict status)
      without copying, writing, or invoking unrpyc.
    - Overwrite protection: if a destination `.rpy`/`.rpym` file already
      exists, decompilation of that file is refused (`OverwriteProtectionError`)
      unless `--force` is given, matching extract_rpa's contract.
    - `--force` additionally backs up any destination file about to be
      overwritten into `<game_root>/.unren/backups/...` (see
      `unren.core.backup`) before invoking unrpyc with `--clobber`.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from unren.adapters import unrpyc as unrpyc_adapter
from unren.core.backup import backup_file
from unren.core.context import PythonRuntime
from unren.core.errors import OutputPathError, OverwriteProtectionError, RuntimeResolutionError
from unren.detection import python as python_detect
from unren.detection.renpy import RenPyGeneration
from unren.detection.rpyc import RpycFileInfo, RpycFormat, find_rpyc_files

# Formats this adapter knows how to hand to unrpyc at all. RPC1/RPC2 are the
# only two container shapes any vendored unrpyc variant understands; anything
# else (RpycFormat.UNKNOWN) is refused per-file, fail-closed.
DECOMPILABLE_FORMATS = (RpycFormat.RPC1, RpycFormat.RPC2)


def _dest_suffix(src: Path) -> str:
    return ".rpym" if src.suffix.lower() == ".rpymc" else ".rpy"


@dataclass
class FilePlan:
    source: str
    destination: str  # the .rpy/.rpym path unrpyc will produce
    rpyc_format: str
    exists: bool
    skipped_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.skipped_reason is None


@dataclass
class DecompileReport:
    game_root: str
    output_root: str
    dry_run: bool
    in_place: bool
    variant: str | None  # "legacy" | "current" | None (unresolved/refused)
    runtime_executable: str | None
    runtime_source: str | None
    files: list[FilePlan] = field(default_factory=list)
    decompiled: int = 0

    @property
    def total_files(self) -> int:
        return len(self.files)

    @property
    def total_failed(self) -> int:
        return sum(1 for f in self.files if not f.ok)


def _default_output_dir(game_root: Path) -> Path:
    return game_root / "unren-decompiled"


def resolve_output_root(
    *, game_root: Path, output: str | None, in_place: bool, game_dir: Path | None = None
) -> Path:
    if in_place and output:
        raise OutputPathError(
            "--output and --in-place are mutually exclusive.", details={"output": output}
        )
    if in_place:
        return game_dir if game_dir is not None else game_root
    if output:
        return Path(output).expanduser()
    return _default_output_dir(game_root)


def _validate_output_dir(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise OutputPathError(
            f"Output path exists and is not a directory: {path}", details={"path": str(path)}
        )


def select_variant_and_runtime(
    generation: RenPyGeneration, *, game_root: Path
) -> tuple[unrpyc_adapter.UnrpycVariant, PythonRuntime]:
    """Pick which vendored unrpyc + which Python runtime to run it with.

    Raises RuntimeResolutionError (fail-closed) if generation is UNKNOWN, or
    if no usable runtime can be resolved for the selected variant(s). Never
    silently guesses.
    """
    if generation is RenPyGeneration.UNKNOWN:
        raise RuntimeResolutionError(
            "Cannot select an unrpyc variant: this game's Ren'Py generation could "
            "not be determined (see `unren detect`). Refusing to guess which "
            "decompiler to run rather than risk mis-decompiling or silently "
            "corrupting output.",
            details={"game_root": str(game_root)},
        )

    if generation is RenPyGeneration.CURRENT:
        runtime = python_detect.resolve_python_runtime(game_root)
        if not runtime.resolved or not _version_at_least(
            runtime.version, python_detect.MIN_UNRPYC_CURRENT_PYTHON
        ):
            raise RuntimeResolutionError(
                "No suitable Python runtime (>=3.9) was found to run the "
                "'current' unrpyc variant required for this Ren'Py >=8 game.",
                details={
                    "game_root": str(game_root),
                    "resolved_version": runtime.version,
                    "resolved_source": runtime.source,
                },
            )
        return unrpyc_adapter.UnrpycVariant.CURRENT, runtime

    # LEGACY generation: prefer a real Python 2 runtime for the "legacy"
    # unrpyc; fall back to "current" + Python 3.9+ when no Python 2 runtime
    # is available (documented known risk - see module docstring).
    py2_runtime = python_detect.resolve_python2_runtime(game_root)
    if py2_runtime.resolved:
        return unrpyc_adapter.UnrpycVariant.LEGACY, py2_runtime

    py3_runtime = python_detect.resolve_python_runtime(game_root)
    if py3_runtime.resolved and _version_at_least(
        py3_runtime.version, python_detect.MIN_UNRPYC_CURRENT_PYTHON
    ):
        return unrpyc_adapter.UnrpycVariant.CURRENT, py3_runtime

    raise RuntimeResolutionError(
        "No suitable Python runtime was found to decompile this Ren'Py <=7 "
        "game: neither a Python 2 runtime (for the 'legacy' unrpyc) nor a "
        "Python >=3.9 runtime (for the 'current' unrpyc fallback) could be "
        "resolved, system-wide or Ren'Py-bundled.",
        details={"game_root": str(game_root)},
    )


def _version_at_least(version: str | None, minimum: tuple[int, ...]) -> bool:
    if not version:
        return False
    parts = []
    for chunk in version.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) >= minimum


def _plan_file(rpyc: RpycFileInfo, *, output_dir: Path, game_root: Path, in_place: bool) -> FilePlan:
    if in_place:
        dest = rpyc.path.with_suffix(_dest_suffix(rpyc.path))
    else:
        try:
            rel = rpyc.path.resolve().relative_to(game_root.resolve())
        except ValueError:
            rel = Path(rpyc.path.name)
        dest = (output_dir / rel).with_suffix(_dest_suffix(rpyc.path))

    plan = FilePlan(
        source=str(rpyc.path),
        destination=str(dest),
        rpyc_format=rpyc.format.value,
        exists=dest.exists(),
    )
    if rpyc.format not in DECOMPILABLE_FORMATS:
        plan.skipped_reason = (
            f"unrecognized RPYC container format ({rpyc.format.value}); refusing to "
            "guess - this file was not passed to unrpyc."
        )
    return plan


def build_plan(
    *,
    game_root: Path,
    game_dir: Path | None,
    generation: RenPyGeneration,
    output: str | None = None,
    in_place: bool = False,
    rpyc_files: list[RpycFileInfo] | None = None,
    variant: unrpyc_adapter.UnrpycVariant | None = None,
    runtime: PythonRuntime | None = None,
) -> DecompileReport:
    """Compute (without mutating anything) the full decompilation plan.

    Raises RuntimeResolutionError (fail-closed) if no unrpyc variant/runtime
    combination can be resolved for `generation` - the plan itself cannot be
    built without knowing which decompiler will run. `variant`/`runtime` may
    be supplied by the caller (e.g. `decompile()`) to avoid re-resolving the
    runtime a second time; when omitted they are resolved here.
    """
    output_root = resolve_output_root(
        game_root=game_root, output=output, in_place=in_place, game_dir=game_dir
    )
    _validate_output_dir(output_root)

    if variant is None or runtime is None:
        variant, runtime = select_variant_and_runtime(generation, game_root=game_root)

    found = rpyc_files if rpyc_files is not None else find_rpyc_files(game_root)
    report = DecompileReport(
        game_root=str(game_root),
        output_root=str(output_root),
        dry_run=True,
        in_place=in_place,
        variant=variant.value,
        runtime_executable=str(runtime.executable) if runtime.executable else None,
        runtime_source=runtime.source,
    )
    for rpyc in found:
        report.files.append(
            _plan_file(rpyc, output_dir=output_root, game_root=game_root, in_place=in_place)
        )
    return report


def _stage_file(source: Path, game_root: Path, output_dir: Path) -> Path:
    """Copy `source` into `output_dir`, preserving its path relative to `game_root`."""
    try:
        rel = source.resolve().relative_to(game_root.resolve())
    except ValueError:
        rel = Path(source.name)
    dest = output_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    return dest


def execute_plan(
    report: DecompileReport,
    *,
    variant: unrpyc_adapter.UnrpycVariant,
    runtime: PythonRuntime,
    force: bool = False,
    try_harder: bool = False,
    timeout: float = unrpyc_adapter.DEFAULT_TIMEOUT_SECONDS,
) -> DecompileReport:
    """Mutate the filesystem according to a previously computed plan.

    Files with unresolved conflicts (existing destination, `force=False`)
    are marked skipped rather than partially decompiled. Files whose
    container format was already flagged unsupported during planning are
    left untouched (never sent to unrpyc).
    """
    game_root = Path(report.game_root)
    output_dir = Path(report.output_root)

    runnable: list[FilePlan] = []
    for plan in report.files:
        if not plan.ok:
            continue
        if plan.exists and not force:
            plan.skipped_reason = OverwriteProtectionError(
                f"Destination file already exists: {plan.destination}; "
                "re-run with --force to overwrite (existing file is backed up first).",
                details={"destination": plan.destination},
            ).message
            continue
        runnable.append(plan)

    if not runnable:
        report.dry_run = False
        return report

    # Stage (copy) input files unless running in-place, then back up any
    # destination we're about to clobber.
    invoke_paths: list[Path] = []
    plan_by_invoke_path: dict[str, FilePlan] = {}
    for plan in runnable:
        src = Path(plan.source)
        if report.in_place:
            invoke_src = src
        else:
            invoke_src = _stage_file(src, game_root, output_dir)
        dest = Path(plan.destination)
        if dest.exists() and force:
            backup_file(game_root, dest)
        invoke_paths.append(invoke_src)
        plan_by_invoke_path[str(invoke_src)] = plan

    result = unrpyc_adapter.run_decompile(
        variant,
        runtime,
        invoke_paths,
        clobber=force,
        try_harder=try_harder,
        timeout=timeout,
    )

    for plan in runnable:
        dest = Path(plan.destination)
        if dest.is_file():
            plan.exists = True
            report.decompiled += 1
        else:
            snippet = (result.stderr or result.stdout or "").strip()
            reason = "unrpyc did not produce the expected output file"
            if snippet:
                reason += f": {snippet[-400:]}"
            plan.skipped_reason = reason

    report.dry_run = False
    return report


def decompile(
    *,
    game_root: Path,
    game_dir: Path | None,
    generation: RenPyGeneration,
    output: str | None = None,
    in_place: bool = False,
    dry_run: bool = False,
    force: bool = False,
    try_harder: bool = False,
    rpyc_files: list[RpycFileInfo] | None = None,
    timeout: float = unrpyc_adapter.DEFAULT_TIMEOUT_SECONDS,
) -> DecompileReport:
    """High-level entry point used by the CLI: plan, then execute unless dry_run."""
    variant, runtime = select_variant_and_runtime(generation, game_root=game_root)
    report = build_plan(
        game_root=game_root,
        game_dir=game_dir,
        generation=generation,
        output=output,
        in_place=in_place,
        rpyc_files=rpyc_files,
        variant=variant,
        runtime=runtime,
    )
    if dry_run:
        return report
    return execute_plan(
        report, variant=variant, runtime=runtime, force=force, try_harder=try_harder, timeout=timeout
    )
