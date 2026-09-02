"""Python runtime resolution (Bauplan §10).

Ren'Py generations bundle different Python versions (Ren'Py <=7 -> Python 2
or early Python 3 depending on build; Ren'Py >=8 -> Python 3.9+). We must not
blindly invoke `python`/`python3` on PATH: the resolver prefers a *suitable*
system interpreter and only falls back to the game's own bundled runtime
under `<root>/lib/<platform>/` when the system one is unusable or absent.

"Suitable" for Milestone 1 purposes means: a working Python 3 interpreter
that meets this project's own minimum (>=3.8, matching Ren'Py 8's own floor)
-- actual invocation of that runtime to run adapters is out of scope until
later milestones (extraction/decompilation). Here we only *resolve and
report* the runtime, per the `doctor`/`detect` acceptance criteria.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from unren.core.context import PythonRuntime

MIN_SYSTEM_PYTHON = (3, 8)

# Candidate system interpreter names, most-specific first.
_SYSTEM_CANDIDATES = ("python3", "python")

# Known relative locations of a Ren'Py-bundled interpreter inside a game's
# `lib/` directory, e.g. lib/linux-x86_64/python or lib/py3-linux-x86_64/python.
_BUNDLED_GLOB_PATTERNS = (
    "lib/*/python3",
    "lib/*/python",
)


def _probe_version(executable: str) -> str | None:
    try:
        proc = subprocess.run(
            [executable, "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _version_tuple(version_str: str) -> tuple[int, ...]:
    parts = []
    for chunk in version_str.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def resolve_system_python() -> PythonRuntime | None:
    """Find a suitable system Python 3 interpreter, or None if unsuitable/absent."""
    for name in _SYSTEM_CANDIDATES:
        path = shutil.which(name)
        if not path:
            continue
        version = _probe_version(path)
        if not version:
            continue
        if _version_tuple(version) >= MIN_SYSTEM_PYTHON:
            return PythonRuntime(executable=Path(path), version=version, source="system")
    return None


def resolve_bundled_python(root: Path) -> PythonRuntime | None:
    """Find a Ren'Py-bundled interpreter under `root/lib/**`, if present."""
    if not root.is_dir():
        return None
    for pattern in _BUNDLED_GLOB_PATTERNS:
        for candidate in root.glob(pattern):
            if not candidate.is_file():
                continue
            version = _probe_version(str(candidate))
            return PythonRuntime(
                executable=candidate, version=version, source="renpy"
            )
    return None


def resolve_python_runtime(root: Path) -> PythonRuntime:
    """Runtime Resolver: prefer suitable system Python, else Ren'Py-bundled, else unresolved."""
    system = resolve_system_python()
    if system is not None:
        return system
    bundled = resolve_bundled_python(root)
    if bundled is not None:
        return bundled
    return PythonRuntime(executable=None, version=None, source="unknown")
