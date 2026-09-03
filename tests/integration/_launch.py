"""Shared, PATH-independent resolution of the `unren` CLI under test.

Regression context (M2 bug): the integration tests used to resolve the
binary under test via `shutil.which("unren")`, i.e. a plain PATH lookup.
When the project's own `.venv` wasn't the *first* entry on PATH (e.g. venv
not activated, but `.venv/bin/pytest` invoked directly by full path), that
silently picked up an older/stale system-installed `unren` instead of the
checkout actually being tested - tests then exercised the wrong build and
either false-failed or, worse, false-passed.

`resolve_unren_cmd()` never performs a PATH lookup. It only ever returns:
  - `[sys.executable, "-m", "unren"]` when PYTHONPATH points at a source
    tree (the project's documented `PYTHONPATH=src pytest ...` invocation,
    and makepkg's check() step, which both run before any install step), or
  - `[str(VENV_UNREN)]`, the repo's own `.venv/bin/unren` by absolute path,
    when that venv exists - regardless of whether it is the active venv or
    what (if anything) `unren` resolves to on PATH, or
  - the `python -m unren` fallback again, for a checkout with neither a
    PYTHONPATH source tree nor a `.venv` (e.g. package installed into the
    current interpreter directly).
`sys.executable` is itself an absolute path chosen by whichever interpreter
is running pytest, so it is likewise never subject to a PATH lookup.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_UNREN = REPO_ROOT / ".venv" / "bin" / "unren"


def resolve_unren_cmd() -> list[str]:
    if os.environ.get("PYTHONPATH"):
        return [sys.executable, "-m", "unren"]
    if VENV_UNREN.is_file():
        return [str(VENV_UNREN)]
    return [sys.executable, "-m", "unren"]  # pragma: no cover - no venv, no PYTHONPATH
