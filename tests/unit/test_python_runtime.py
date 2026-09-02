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
