"""Unit tests for unren.detection.python (system/bundled runtime resolution)."""

from __future__ import annotations

from pathlib import Path

from unren.detection.python import resolve_python_runtime, resolve_system_python


def test_resolve_system_python_finds_something_in_ci() -> None:
    # The venv this test suite runs under always has python3 on PATH.
    runtime = resolve_system_python()
    assert runtime is not None
    assert runtime.source == "system"
    assert runtime.executable is not None
    assert runtime.version is not None


def test_resolve_python_runtime_prefers_system(tmp_path: Path) -> None:
    runtime = resolve_python_runtime(tmp_path)
    assert runtime.source == "system"
    assert runtime.resolved is True


def test_resolve_python_runtime_unknown_when_nothing_available(tmp_path: Path, monkeypatch) -> None:
    import unren.detection.python as python_detect

    monkeypatch.setattr(python_detect, "resolve_system_python", lambda: None)
    monkeypatch.setattr(python_detect, "resolve_bundled_python", lambda root: None)

    runtime = python_detect.resolve_python_runtime(tmp_path)
    assert runtime.source == "unknown"
    assert runtime.resolved is False


def test_resolve_system_python2_absent_returns_none() -> None:
    # This CI/dev environment does not ship a system python2 (documented
    # known risk on the Milestone 3 task card) - resolve_system_python2()
    # must return None cleanly rather than raising or crashing.
    from unren.detection.python import resolve_system_python2

    result = resolve_system_python2()
    assert result is None or result.source == "system"


def test_resolve_python2_runtime_unknown_when_nothing_available(tmp_path: Path, monkeypatch) -> None:
    import unren.detection.python as python_detect

    monkeypatch.setattr(python_detect, "resolve_system_python2", lambda: None)
    monkeypatch.setattr(python_detect, "resolve_bundled_python2", lambda root: None)

    runtime = python_detect.resolve_python2_runtime(tmp_path)
    assert runtime.source == "unknown"
    assert runtime.resolved is False


def test_resolve_python2_runtime_prefers_system_when_available(tmp_path: Path, monkeypatch) -> None:
    import unren.detection.python as python_detect
    from unren.core.context import PythonRuntime

    fake = PythonRuntime(executable=Path("/usr/bin/python2"), version="2.7.18", source="system")
    monkeypatch.setattr(python_detect, "resolve_system_python2", lambda: fake)
    monkeypatch.setattr(python_detect, "resolve_bundled_python2", lambda root: None)

    runtime = python_detect.resolve_python2_runtime(tmp_path)
    assert runtime is fake
    assert runtime.source == "system"


def test_resolve_python2_runtime_falls_back_to_bundled(tmp_path: Path, monkeypatch) -> None:
    import unren.detection.python as python_detect
    from unren.core.context import PythonRuntime

    fake = PythonRuntime(executable=tmp_path / "lib" / "linux-x86_64" / "python", version="2.7.13", source="renpy")
    monkeypatch.setattr(python_detect, "resolve_system_python2", lambda: None)
    monkeypatch.setattr(python_detect, "resolve_bundled_python2", lambda root: fake)

    runtime = python_detect.resolve_python2_runtime(tmp_path)
    assert runtime is fake
    assert runtime.source == "renpy"


def test_resolve_bundled_python2_filters_out_python3_bundle(tmp_path: Path, monkeypatch) -> None:
    """A bundled `lib/*/python` that turns out to be Python 3 must not be
    reported as a resolved Python 2 runtime - only the probed version counts,
    not the filename."""
    import unren.detection.python as python_detect

    bundle_dir = tmp_path / "lib" / "linux-x86_64"
    bundle_dir.mkdir(parents=True)
    fake_interp = bundle_dir / "python"
    fake_interp.write_text("#!/bin/sh\n")
    fake_interp.chmod(0o755)

    monkeypatch.setattr(python_detect, "_probe_version", lambda executable: "3.9.10")

    result = python_detect.resolve_bundled_python2(tmp_path)
    assert result is None


def test_resolve_bundled_python2_accepts_real_python2_bundle(tmp_path: Path, monkeypatch) -> None:
    import unren.detection.python as python_detect

    bundle_dir = tmp_path / "lib" / "linux-x86_64"
    bundle_dir.mkdir(parents=True)
    fake_interp = bundle_dir / "python"
    fake_interp.write_text("#!/bin/sh\n")
    fake_interp.chmod(0o755)

    monkeypatch.setattr(python_detect, "_probe_version", lambda executable: "2.7.18")

    result = python_detect.resolve_bundled_python2(tmp_path)
    assert result is not None
    assert result.source == "renpy"
    assert result.version == "2.7.18"
