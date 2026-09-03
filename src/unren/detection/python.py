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

# Milestone 3: the vendored "current" unrpyc (v2.0.3) hard-requires 3.9+ at
# its own top of main() ("must be executed with Python 3.9 or later"). This
# is stricter than this project's own general MIN_SYSTEM_PYTHON floor, so
# callers that specifically need to invoke the current unrpyc variant should
# check against this constant rather than MIN_SYSTEM_PYTHON.
MIN_UNRPYC_CURRENT_PYTHON = (3, 9)

# Candidate system interpreter names, most-specific first.
_SYSTEM_CANDIDATES = ("python3", "python")

# Candidate system interpreter names for a Python *2* runtime, needed only to
# run the vendored "legacy" unrpyc (v1.3.2, real python2 syntax - not merely
# python2-flavored python3-compatible code). Most modern Linux distros no
# longer ship a system python2 at all; this is expected and documented as a
# known risk (task card "Bekannte Risiken") - the bundled-runtime fallback
# below is the primary way this ever resolves in practice.
_SYSTEM_PYTHON2_CANDIDATES = ("python2", "python2.7")

# Known relative locations of a Ren'Py-bundled interpreter inside a game's
# `lib/` directory, e.g. lib/linux-x86_64/python or lib/py3-linux-x86_64/python.
_BUNDLED_GLOB_PATTERNS = (
    "lib/*/python3",
    "lib/*/python",
)

# Same idea, but any candidate whose probed version turns out to start with
# "2." is what resolve_bundled_python2() is looking for. Older Ren'Py (<=7)
# games commonly bundle their interpreter as plain `lib/<platform>/python`
# with no "3" marker, which is exactly what "lib/*/python" also matches -
# resolve_bundled_python2() reuses the same glob but filters by probed
# major version instead of by filename.
_BUNDLED_PYTHON2_GLOB_PATTERNS = (
    "lib/*/python2",
    "lib/*/python2.7",
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


def resolve_system_python2() -> PythonRuntime | None:
    """Find a system Python *2* interpreter, or None if unsuitable/absent.

    Unlike resolve_system_python(), there is no minimum-version floor here -
    any successfully-probed 2.x interpreter is accepted, since python2 itself
    has been EOL/frozen since 2020 and further version-gating would just make
    an already-scarce resource harder to find.
    """
    for name in _SYSTEM_PYTHON2_CANDIDATES:
        path = shutil.which(name)
        if not path:
            continue
        version = _probe_version(path)
        if not version:
            continue
        if _version_tuple(version)[:1] == (2,):
            return PythonRuntime(executable=Path(path), version=version, source="system")
    return None


def resolve_bundled_python2(root: Path) -> PythonRuntime | None:
    """Find a Ren'Py-bundled Python *2* interpreter under `root/lib/**`, if present.

    Filters candidates (which may include plain `lib/*/python` - ambiguous by
    name alone between an old py2 bundle and certain py3 bundles that also
    use the unversioned name) by actually probing the reported version.
    """
    if not root.is_dir():
        return None
    for pattern in _BUNDLED_PYTHON2_GLOB_PATTERNS:
        for candidate in root.glob(pattern):
            if not candidate.is_file():
                continue
            version = _probe_version(str(candidate))
            if not version or _version_tuple(version)[:1] != (2,):
                continue
            return PythonRuntime(executable=candidate, version=version, source="renpy")
    return None


def resolve_python2_runtime(root: Path) -> PythonRuntime:
    """Runtime Resolver for a Python *2* interpreter specifically.

    Needed only for the vendored "legacy" unrpyc (v1.3.2), which is real
    Python-2-only source (not merely old-style-compatible Python 3). Same
    system-first, bundled-fallback shape as resolve_python_runtime(), but
    never returns a Python 3 interpreter even if one is all that's available.
    Returns a PythonRuntime with source="unknown" (unresolved) rather than
    raising - callers decide whether that's fatal for the operation at hand.
    """
    system = resolve_system_python2()
    if system is not None:
        return system
    bundled = resolve_bundled_python2(root)
    if bundled is not None:
        return bundled
    return PythonRuntime(executable=None, version=None, source="unknown")
