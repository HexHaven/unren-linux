"""End-to-end integration tests invoking the real unren CLI against fixtures.

Uses subprocess against the installed `unren` console script so we exercise the
actual packaging/entry-point wiring, not just the in-process argparse logic.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

UNREN_EXE = shutil.which("unren")


def _run_unren(*args: str) -> subprocess.CompletedProcess:
    if UNREN_EXE:
        cmd = [UNREN_EXE, *args]
    else:  # pragma: no cover - fallback if not installed as a script somehow
        cmd = [sys.executable, "-m", "unren", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def test_json_flag_after_subcommand(renpy8_game: Path) -> None:
    # Regression test: --json used to only be accepted BEFORE the subcommand
    # (`unren --json doctor`); `unren doctor --json` raised an argparse error.
    proc = _run_unren("doctor", "--json", str(renpy8_game))
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["ok"] is True


def test_version_flag() -> None:
    proc = _run_unren("--version")
    assert proc.returncode == 0
    assert "unren" in proc.stdout


def test_detect_renpy6_fixture_text(renpy6_game: Path) -> None:
    proc = _run_unren("detect", str(renpy6_game))
    assert proc.returncode == 0
    assert "Game found:      yes" in proc.stdout
    assert "legacy" in proc.stdout
    assert "major 6" in proc.stdout


def test_detect_renpy8_fixture_json(renpy8_game: Path) -> None:
    proc = _run_unren("--json", "detect", str(renpy8_game))
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    value = data["value"]
    # is_game is a computed @property on GameContext, not a dataclass field, so
    # it isn't present in the JSON serialization - check the underlying fields
    # it derives from instead.
    assert value["game_dir"] is not None
    assert value["renpy_version"]["generation"] == "current"
    assert value["renpy_version"]["major"] == 8
    assert value["archives"], "expected at least one archive reported"


def test_detect_renpy7_fixture_json(renpy7_game: Path) -> None:
    proc = _run_unren("--json", "detect", str(renpy7_game))
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    value = data["value"]
    assert value["renpy_version"]["generation"] == "legacy"
    assert value["renpy_version"]["major"] == 7


def test_detect_non_game_dir_reports_no_game(non_game_dir: Path) -> None:
    proc = _run_unren("detect", str(non_game_dir))
    # cmd_detect returns exit code 2 when a path is valid but not recognized as a game.
    assert proc.returncode == 2
    assert "Game found:      no" in proc.stdout


def test_detect_missing_path_fails() -> None:
    proc = _run_unren("detect", "/definitely/does/not/exist/anywhere")
    assert proc.returncode == 1
    assert "error" in (proc.stdout + proc.stderr).lower()


@pytest.mark.parametrize("fixture_name", ["renpy6_game", "renpy7_game", "renpy8_game"])
def test_doctor_json_on_each_fixture(request, fixture_name: str) -> None:
    game_dir: Path = request.getfixturevalue(fixture_name)
    proc = _run_unren("--json", "doctor", str(game_dir))
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    diagnosis = data["value"]

    assert "os" in diagnosis
    assert diagnosis["os"]["system"] == "Linux"
    assert diagnosis["game_found"] is True
    assert diagnosis["game"] is not None
    assert "python_runtime" in diagnosis["game"]
    assert "tools" in diagnosis
    assert isinstance(diagnosis["tools"], dict)
    assert "archive_formats_present" in diagnosis["game"]


def test_doctor_json_no_game_path(non_game_dir: Path) -> None:
    proc = _run_unren("--json", "doctor", str(non_game_dir))
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    diagnosis = data["value"]
    assert diagnosis["game_found"] is False


def test_doctor_text_smoke(tmp_path: Path) -> None:
    proc = _run_unren("doctor", str(tmp_path))
    assert proc.returncode == 0
    assert "unren doctor" in proc.stdout
    assert "OS:" in proc.stdout
    assert "Tools available:" in proc.stdout


def test_stub_subcommand_reports_not_implemented(renpy8_game: Path) -> None:
    proc = _run_unren("extract", str(renpy8_game))
    assert proc.returncode == 3
    assert "not yet implemented" in (proc.stdout + proc.stderr)


def test_bare_invocation_prints_help_and_exits_3() -> None:
    proc = _run_unren()
    assert proc.returncode == 3
    assert "usage" in (proc.stdout + proc.stderr).lower()
