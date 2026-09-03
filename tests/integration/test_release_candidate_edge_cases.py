"""Milestone 7 (Release Candidate) integration tests: error-path determinism.

Scope per the M7 task card: fail-closed, never-silent-fail behavior for
edge cases not already covered by earlier milestones' test suites -
specifically a read-only filesystem/mount surfacing as a structured error
(not a raw Python traceback) through the CLI's top-level error boundary,
plus confirmation that `--dry-run` never touches the filesystem even when
the target is unwritable (so it can't ever crash on read-only media either).

Unicode/space-in-path, corrupt-archive, and unknown-Ren'Py-generation edge
cases are already covered by test_rpatool_adapter.py, test_rpyc_detection.py,
and existing test_cli.py cases (test_extract_paths_with_spaces_and_unicode,
test_decompile_unknown_format_reported_as_error_not_skipped) - not
duplicated here.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

UNREN_EXE = shutil.which("unren")


def _run_unren(*args: str) -> subprocess.CompletedProcess:
    cmd = [UNREN_EXE, *args] if UNREN_EXE else [sys.executable, "-m", "unren", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def _make_renpy8_game(tmp_path: Path) -> Path:
    root = tmp_path / "game_root"
    (root / "game").mkdir(parents=True)
    (root / "renpy").mkdir(parents=True)
    (root / "renpy" / "version.py").write_text(
        "version_tuple = (8, 2, 0, 'vanilla')\n", encoding="utf-8"
    )
    return root


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses filesystem permission checks")
def test_patch_action_readonly_game_dir_reports_structured_error_not_crash(tmp_path: Path) -> None:
    """A read-only game/ dir must yield a clean exit-1 + message, never a traceback.

    Regression test for the M7 bugfix: cmd_patch_action's write to
    game/unren-console.rpy previously let a bare PermissionError (OSError)
    propagate all the way out of main() as an unhandled traceback -a
    silent-fail-adjacent crash that violates this project's own
    "deterministic error behavior, never a crash" acceptance bar. main()
    now wraps any OSError escaping command dispatch into the same
    UnrenError/Result contract every other error already uses.
    """
    root = _make_renpy8_game(tmp_path)
    game_dir = root / "game"
    game_dir.chmod(0o555)
    try:
        proc = _run_unren("console", "enable", str(root))
        assert proc.returncode == 1
        assert "Traceback" not in proc.stderr
        assert "Traceback" not in proc.stdout
        assert proc.stderr.strip() != "" or proc.stdout.strip() != ""
    finally:
        game_dir.chmod(0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses filesystem permission checks")
def test_patch_action_readonly_game_dir_json_error_shape(tmp_path: Path) -> None:
    root = _make_renpy8_game(tmp_path)
    game_dir = root / "game"
    game_dir.chmod(0o555)
    try:
        proc = _run_unren("--json", "console", "enable", str(root))
        assert proc.returncode == 1
        data = json.loads(proc.stdout)
        assert data["ok"] is False
        assert data["error"]["code"] in ("filesystem-error",)
        assert "message" in data["error"] and data["error"]["message"]
    finally:
        game_dir.chmod(0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses filesystem permission checks")
def test_extract_readonly_output_parent_reports_structured_error_not_crash(tmp_path: Path) -> None:
    """extract's default-output-dir mkdir() under a read-only game_root must not crash."""
    root = _make_renpy8_game(tmp_path)
    from tests.helpers.rpa_builder import build_archive

    build_archive(root / "game" / "archive.rpa", {"script.rpy": b"label start:\n    return\n"}, version="RPA-3.0")
    root.chmod(0o555)
    try:
        proc = _run_unren("--json", "extract", str(root))
        assert proc.returncode == 1
        assert "Traceback" not in proc.stdout and "Traceback" not in proc.stderr
        data = json.loads(proc.stdout)
        assert data["ok"] is False
    finally:
        root.chmod(0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses filesystem permission checks")
def test_extract_dry_run_reliable_under_readonly_filesystem(tmp_path: Path) -> None:
    """--dry-run must succeed and make zero filesystem changes even when the
    target tree is read-only - it must never need to write anything, so a
    read-only mount can never break it (the actual "reliable regardless of
    environment" guarantee the M7 acceptance criteria ask for).
    """
    root = _make_renpy8_game(tmp_path)
    from tests.helpers.rpa_builder import build_archive

    build_archive(root / "game" / "archive.rpa", {"script.rpy": b"label start:\n    return\n"}, version="RPA-3.0")
    before = sorted(str(p) for p in root.rglob("*"))
    root.chmod(0o555)
    try:
        proc = _run_unren("--json", "--dry-run", "extract", str(root))
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert data["ok"] is True
        assert data["value"]["dry_run"] is True
        assert data["value"]["archives"][0]["extracted"] == 0
    finally:
        root.chmod(0o755)
    after = sorted(str(p) for p in root.rglob("*"))
    assert before == after


def test_doctor_never_crashes_on_nonexistent_path(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist_at_all"
    proc = _run_unren("--json", "doctor", str(missing))
    assert proc.returncode == 0
    assert "Traceback" not in proc.stdout and "Traceback" not in proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["value"]["game_found"] is False
    assert data["value"]["detection_error"]


def test_doctor_reports_unknown_generation_not_crash(tmp_path: Path) -> None:
    """A `game/` dir with zero Ren'Py markers must report generation=unknown, not crash."""
    game_root = tmp_path / "mystery_game"
    (game_root / "game").mkdir(parents=True)
    (game_root / "game" / "readme.txt").write_text("no renpy markers here\n", encoding="utf-8")

    proc = _run_unren("--json", "doctor", str(game_root))
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["value"]["game"]["renpy_generation"] == "unknown"


def test_decompile_unknown_generation_refuses_with_clear_reason_not_crash(tmp_path: Path) -> None:
    """decompile on a game whose Ren'Py generation can't be determined must fail
    closed with a clear, actionable reason - never silently pick a decompiler
    variant or crash.
    """
    game_root = tmp_path / "mystery_game"
    game_dir = game_root / "game"
    game_dir.mkdir(parents=True)
    (game_dir / "script.rpyc").write_bytes(b"not a real rpyc container at all")

    proc = _run_unren("--json", "decompile", str(game_root))
    assert proc.returncode == 1
    assert "Traceback" not in proc.stdout and "Traceback" not in proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is False
    assert data["error"]["message"]
