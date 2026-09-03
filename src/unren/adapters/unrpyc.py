"""Adapter around the vendored unrpyc decompiler (Milestone 3).

Provenance
----------
Vendors two pinned upstream releases of ``CensoredUsername/unrpyc`` (MIT
license) verbatim, matching the exact pins upstream UnRen-forall itself
resolved to per docs/UPSTREAM-BEHAVIOR.md §1 / §7.7 / §7.8:

- **legacy** variant: tag ``v1.3.2`` (real Python 2 source; targets the RPC2
  pickle layout as understood by Ren'Py <=7-era ``unrpyc``, the version
  upstream's own comment header self-identifies as
  ``"Unrpyc Legacy for Ren'Py v7 and lower"``). Vendored verbatim at
  ``src/unren/vendor/unrpyc_legacy/``.
- **current** variant: tag ``v2.0.3`` (Python 3.9+ only; upstream's own
  ``main()`` refuses to run under anything older). Still *attempts*
  Ren'Py-7-era RPC2 files - it warns rather than refuses when it detects
  Python-2-pickled content, see its own ``read_ast_from_file()`` - but the
  matrix confirms upstream UnRen-forall selects this variant specifically
  when the game's *bundled Python* is 3.x, independent of the Ren'Py major
  version (docs/UPSTREAM-BEHAVIOR.md §7.7). Vendored verbatim at
  ``src/unren/vendor/unrpyc_current/``.

Per Bauplan §12 ("keine undokumentierten Vendor-Blobs"), both trees are
byte-identical copies of the tagged GitHub releases (verified against the
release tarballs, not just ``master`` HEAD - ``master`` and ``v2.0.3`` were
confirmed identical for all source files at vendoring time). See
``src/unren/vendor/README.md`` for full provenance notes.

This module never reimplements unrpyc's own decompilation logic. It only:

1. resolves which vendored copy + which Python runtime generation
   (Milestone 3's ``RuntimeResolver`` extension, ``unren.detection.python``)
   should run it,
2. builds and runs the subprocess invocation,
3. interprets the resulting filesystem state (did the expected ``.rpy``/
   ``.rpym`` output file appear?) rather than parsing unrpyc's own ad-hoc
   human-readable log output, which is not a stable machine interface.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from unren.core.context import PythonRuntime
from unren.core.errors import UnrenError

#: Root of the vendored unrpyc copies: src/unren/vendor/
VENDOR_ROOT = Path(__file__).resolve().parent.parent / "vendor"

DEFAULT_TIMEOUT_SECONDS = 300


class UnrpycError(UnrenError):
    code = "unrpyc-error"


class UnrpycRuntimeError(UnrpycError):
    """The resolved Python runtime cannot run the selected vendored unrpyc."""

    code = "unrpyc-runtime-error"


class UnrpycInvocationError(UnrpycError):
    """The unrpyc subprocess itself could not be started or timed out."""

    code = "unrpyc-invocation-error"


class UnrpycVariant(str, Enum):
    """Which vendored unrpyc copy to use - mirrors RenPyGeneration, but is a
    separate concept: selection is driven by the resolved Python runtime
    generation (per docs/UPSTREAM-BEHAVIOR.md §7.7), which correlates with
    but is not identical to the game's Ren'Py major version.
    """

    LEGACY = "legacy"
    CURRENT = "current"


def vendor_dir(variant: UnrpycVariant) -> Path:
    """Return the vendored source directory for `variant`."""
    name = "unrpyc_legacy" if variant is UnrpycVariant.LEGACY else "unrpyc_current"
    return VENDOR_ROOT / name


def vendor_entrypoint(variant: UnrpycVariant) -> Path:
    """Return the vendored `unrpyc.py` script path for `variant`."""
    return vendor_dir(variant) / "unrpyc.py"


@dataclass
class DecompileInvocationResult:
    """Raw result of one unrpyc subprocess invocation (a batch of files)."""

    returncode: int
    stdout: str
    stderr: str
    command: list[str] = field(default_factory=list)
    timed_out: bool = False


def build_command(
    variant: UnrpycVariant,
    runtime: PythonRuntime,
    files: list[Path],
    *,
    clobber: bool = False,
    try_harder: bool = False,
) -> list[str]:
    """Build the subprocess argv to decompile `files` with the vendored unrpyc.

    Raises UnrpycRuntimeError if `runtime` has no resolved executable - a
    command cannot be built without an interpreter to run it with.
    """
    if runtime.executable is None:
        raise UnrpycRuntimeError(
            "Cannot build an unrpyc invocation: no Python runtime was resolved "
            f"for the '{variant.value}' unrpyc variant.",
            details={"variant": variant.value},
        )
    if not files:
        raise UnrpycError("Cannot build an unrpyc invocation with an empty file list.")

    entrypoint = vendor_entrypoint(variant)
    cmd = [str(runtime.executable), str(entrypoint)]
    if clobber:
        cmd.append("--clobber")
    if try_harder:
        cmd.append("--try-harder")
    cmd.extend(str(f) for f in files)
    return cmd


def run_decompile(
    variant: UnrpycVariant,
    runtime: PythonRuntime,
    files: list[Path],
    *,
    clobber: bool = False,
    try_harder: bool = False,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> DecompileInvocationResult:
    """Invoke the vendored unrpyc against `files` as a single batch subprocess call.

    Batching (rather than one subprocess per file) lets unrpyc's own internal
    multiprocessing worker pool parallelize the work, matching upstream's
    own invocation shape (`unrpyc.py file1.rpyc file2.rpyc ...`).

    Success/failure of *individual* files is not parsed from stdout here -
    the caller (unren.actions.decompile_rpyc) determines per-file success by
    checking whether the expected output file materialized on disk. This
    function only reports whether the subprocess itself ran and how it
    exited.
    """
    cmd = build_command(variant, runtime, files, clobber=clobber, try_harder=try_harder)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(vendor_dir(variant)),
        )
    except subprocess.TimeoutExpired as exc:
        timeout_stdout = str(exc.stdout) if exc.stdout else ""
        timeout_stderr = str(exc.stderr) if exc.stderr else ""
        return DecompileInvocationResult(
            returncode=-1,
            stdout=timeout_stdout,
            stderr=timeout_stderr + f"\n[unren] unrpyc invocation timed out after {timeout}s",
            command=cmd,
            timed_out=True,
        )
    except OSError as exc:
        raise UnrpycInvocationError(
            f"Could not start unrpyc subprocess: {exc}",
            details={"command": cmd},
        ) from exc

    return DecompileInvocationResult(
        returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr, command=cmd
    )
