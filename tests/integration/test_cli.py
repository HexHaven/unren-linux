"""End-to-end integration tests invoking the real unren CLI against fixtures.

Uses subprocess against the installed `unren` console script so we exercise the
actual packaging/entry-point wiring, not just the in-process argparse logic.
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


def _run_unren(
    *args: str, input: str | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    if UNREN_EXE:
        cmd = [UNREN_EXE, *args]
    else:  # pragma: no cover - fallback if not installed as a script somehow
        cmd = [sys.executable, "-m", "unren", *args]
    run_env = None
    if env is not None:
        run_env = dict(os.environ)
        run_env.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30, input=input, env=run_env)


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


def test_console_enable_requires_subaction(renpy8_game: Path) -> None:
    proc = _run_unren("console")
    assert proc.returncode == 2
    assert "sub-action" in (proc.stdout + proc.stderr).lower()


def test_decompile_no_rpyc_found(renpy8_game: Path) -> None:
    # renpy8_game fixture has no .rpyc files, only an .rpa archive.
    proc = _run_unren("decompile", str(renpy8_game))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "No .rpyc/.rpymc files found" in proc.stdout


def test_bare_invocation_starts_interactive_menu_and_exits_0_on_immediate_eof() -> None:
    # Milestone 5: bare `unren` (no subcommand) launches the interactive
    # menu (ui/interactive.py) instead of just printing help. Feeding an
    # immediately-closed stdin (empty input) simulates the user hitting
    # Ctrl-D at the first prompt, which the menu loop treats as a clean quit.
    proc = _run_unren(input="")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "unren" in proc.stdout.lower()


def test_bare_invocation_menu_lists_core_actions_and_quits_on_q() -> None:
    proc = _run_unren(input="q\n")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = proc.stdout
    assert "detect" in out.lower()
    assert "diagnostics" in out.lower()  # menu.option.doctor label
    assert "extract" in out.lower()


def _build_rpa_game(tmp_path: Path, *, version: str = "RPA-3.0") -> Path:
    from tests.helpers.rpa_builder import build_archive

    game_root = tmp_path / "TestGame"
    game_dir = game_root / "game"
    game_dir.mkdir(parents=True)
    (game_root / "renpy").mkdir()
    (game_root / "renpy" / "version.py").write_text('version = "8.1.0"\n')
    build_archive(game_dir / "archive.rpa", {"script.rpyc": b"payload data"}, version=version)
    return game_root


def test_extract_creates_default_output_dir(tmp_path: Path) -> None:
    game_root = _build_rpa_game(tmp_path)
    proc = _run_unren("extract", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out_file = game_root / "unren-extracted" / "script.rpyc"
    assert out_file.read_bytes() == b"payload data"


def test_extract_custom_output_flag(tmp_path: Path) -> None:
    game_root = _build_rpa_game(tmp_path)
    custom_out = tmp_path / "custom" / "out"
    proc = _run_unren("extract", "--output", str(custom_out), str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (custom_out / "script.rpyc").read_bytes() == b"payload data"
    assert not (game_root / "unren-extracted").exists()


def test_extract_dry_run_makes_no_changes(tmp_path: Path) -> None:
    game_root = _build_rpa_game(tmp_path)
    proc = _run_unren("--dry-run", "extract", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "dry-run" in proc.stdout.lower() or "would extract" in proc.stdout.lower()
    assert not (game_root / "unren-extracted").exists()


def test_extract_json_output(tmp_path: Path) -> None:
    game_root = _build_rpa_game(tmp_path)
    proc = _run_unren("--json", "extract", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["value"]["archives"]
    assert data["value"]["archives"][0]["extracted"] == 1


def test_extract_no_overwrite_without_force(tmp_path: Path) -> None:
    game_root = _build_rpa_game(tmp_path)
    out_dir = game_root / "unren-extracted"
    out_dir.mkdir()
    (out_dir / "script.rpyc").write_text("pre-existing, must survive")

    proc = _run_unren("extract", str(game_root))
    assert proc.returncode != 0
    assert (out_dir / "script.rpyc").read_text() == "pre-existing, must survive"


def test_extract_in_place_flag(tmp_path: Path) -> None:
    game_root = _build_rpa_game(tmp_path)
    proc = _run_unren("extract", "--in-place", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (game_root / "game" / "script.rpyc").read_bytes() == b"payload data"
    assert not (game_root / "unren-extracted").exists()


def test_extract_rpa_v2_and_v3_fixtures(tmp_path: Path) -> None:
    for version in ("RPA-2.0", "RPA-3.0"):
        game_root = _build_rpa_game(tmp_path / version, version=version)
        proc = _run_unren("extract", str(game_root))
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert (game_root / "unren-extracted" / "script.rpyc").read_bytes() == b"payload data"


def test_extract_paths_with_spaces_and_unicode(tmp_path: Path) -> None:
    game_root = _build_rpa_game(tmp_path / "gäme with spaces")
    proc = _run_unren("extract", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (game_root / "unren-extracted" / "script.rpyc").read_bytes() == b"payload data"


def test_extract_no_archives_found(tmp_path: Path) -> None:
    game_root = tmp_path / "EmptyGame"
    (game_root / "game").mkdir(parents=True)
    proc = _run_unren("extract", str(game_root))
    assert proc.returncode == 0
    assert "No RPA archives found" in proc.stdout


RPYC_FIXTURES = Path(__file__).parent.parent / "fixtures" / "rpyc_samples"


def _build_decompile_game(tmp_path: Path, *, generation_major: str = "8.1.0") -> Path:
    game_root = tmp_path / "DecompileGame"
    game_dir = game_root / "game"
    game_dir.mkdir(parents=True)
    (game_root / "renpy").mkdir()
    (game_root / "renpy" / "version.py").write_text(f'version = "{generation_major}"\n')
    (game_dir / "options.rpyc").write_bytes((RPYC_FIXTURES / "current8_options.rpyc").read_bytes())
    return game_root


def test_decompile_creates_default_output_dir(tmp_path: Path) -> None:
    game_root = _build_decompile_game(tmp_path)
    proc = _run_unren("decompile", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out_file = game_root / "unren-decompiled" / "game" / "options.rpy"
    assert out_file.is_file()
    assert len(out_file.read_text(encoding="utf-8")) > 0


def test_decompile_dry_run_makes_no_changes(tmp_path: Path) -> None:
    game_root = _build_decompile_game(tmp_path)
    proc = _run_unren("--dry-run", "decompile", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "dry-run" in proc.stdout.lower() or "would decompile" in proc.stdout.lower()
    assert not (game_root / "unren-decompiled").exists()
    # original .rpyc must survive untouched
    assert (game_root / "game" / "options.rpyc").read_bytes() == (
        RPYC_FIXTURES / "current8_options.rpyc"
    ).read_bytes()


def test_decompile_json_output(tmp_path: Path) -> None:
    game_root = _build_decompile_game(tmp_path)
    proc = _run_unren("--json", "decompile", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["value"]["files"]
    assert data["value"]["files"][0]["rpyc_format"] == "rpc2"
    assert data["value"]["decompiled"] == 1


def test_decompile_in_place_flag(tmp_path: Path) -> None:
    game_root = _build_decompile_game(tmp_path)
    proc = _run_unren("decompile", "--in-place", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (game_root / "game" / "options.rpy").is_file()
    assert not (game_root / "unren-decompiled").exists()


def test_decompile_no_overwrite_without_force(tmp_path: Path) -> None:
    game_root = _build_decompile_game(tmp_path)
    out_dir = game_root / "unren-decompiled" / "game"
    out_dir.mkdir(parents=True)
    (out_dir / "options.rpy").write_text("pre-existing, must survive")

    proc = _run_unren("decompile", str(game_root))
    assert proc.returncode != 0
    assert (out_dir / "options.rpy").read_text() == "pre-existing, must survive"


def test_decompile_legacy_generation_fixture(tmp_path: Path) -> None:
    # Ren'Py 7-era fixture: LEGACY generation with no python2 runtime
    # available in this environment falls back to the vendored 'current'
    # unrpyc, which successfully handles the real RPC2 sample (verified
    # unit-level in test_unrpyc_adapter.py) - exercised here end-to-end
    # through the actual CLI subprocess.
    game_root = tmp_path / "LegacyGame"
    game_dir = game_root / "game"
    game_dir.mkdir(parents=True)
    (game_root / "renpy").mkdir()
    (game_root / "renpy" / "version.py").write_text('version = "7.4.11"\n')
    (game_dir / "script.rpyc").write_bytes((RPYC_FIXTURES / "legacy7_options.rpyc").read_bytes())

    proc = _run_unren("decompile", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out_file = game_root / "unren-decompiled" / "game" / "script.rpy"
    assert out_file.is_file()


def test_decompile_unknown_format_reported_as_error_not_skipped(tmp_path: Path) -> None:
    game_root = _build_decompile_game(tmp_path)
    (game_root / "game" / "corrupt.rpyc").write_bytes(b"totally bogus rpyc content, not a real container")

    proc = _run_unren("--json", "decompile", str(game_root))
    data = json.loads(proc.stdout)
    files = data["value"]["files"]
    corrupt_entry = next(f for f in files if f["source"].endswith("corrupt.rpyc"))
    assert corrupt_entry["skipped_reason"] is not None
    assert "unrecognized" in corrupt_entry["skipped_reason"]
    # the valid file must still have been processed successfully alongside it
    good_entry = next(f for f in files if f["source"].endswith("options.rpyc"))
    assert good_entry["skipped_reason"] is None


def _build_patch_game(tmp_path: Path) -> Path:
    game_root = tmp_path / "PatchGame"
    game_dir = game_root / "game"
    game_dir.mkdir(parents=True)
    (game_root / "renpy").mkdir()
    (game_root / "renpy" / "version.py").write_text('version = "8.1.0"\n')
    return game_root


@pytest.mark.parametrize(
    "command,marker_filename,expected_substring",
    [
        ("console", "unren-console.rpy", "config.console = True"),
        ("devmode", "unren-debug.rpy", "config.debug = True"),
        ("skip", "unren-skip.rpy", "allow_skipping"),
        ("skipall", "unren-skipall.rpy", "_preferences.transitions"),
        ("rollback", "unren-rollback.rpy", "rollback_enabled"),
        ("quicksave", "unren-quicksave.rpy", "QuickSave"),
        ("quickmenu", "unren-qmenu.rpy", "quick_menu"),
        ("nosync", "unren-nsync.rpy", "has_sync"),
    ],
)
def test_patch_action_enable_writes_marker(
    tmp_path: Path, command: str, marker_filename: str, expected_substring: str
) -> None:
    game_root = _build_patch_game(tmp_path)
    proc = _run_unren(command, "enable", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    marker = game_root / "game" / marker_filename
    assert marker.is_file()
    assert expected_substring in marker.read_text()


def test_patch_action_enable_idempotent(tmp_path: Path) -> None:
    game_root = _build_patch_game(tmp_path)
    proc1 = _run_unren("console", "enable", str(game_root))
    assert proc1.returncode == 0
    proc2 = _run_unren("console", "enable", str(game_root))
    assert proc2.returncode == 0
    assert "already present" in (proc2.stdout + proc2.stderr).lower()


def test_patch_action_dry_run_writes_nothing(tmp_path: Path) -> None:
    game_root = _build_patch_game(tmp_path)
    proc = _run_unren("--dry-run", "console", "enable", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not (game_root / "game" / "unren-console.rpy").exists()


def test_patch_action_json_output(tmp_path: Path) -> None:
    game_root = _build_patch_game(tmp_path)
    proc = _run_unren("--json", "skip", "enable", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["value"]["applied"] is True


def test_cleanup_restore_no_backups_not_error(tmp_path: Path) -> None:
    game_root = _build_patch_game(tmp_path)
    proc = _run_unren("cleanup", "restore", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Nothing to do" in proc.stdout


def test_cleanup_restore_moves_backup_back(tmp_path: Path) -> None:
    game_root = _build_rpa_game(tmp_path)
    out_dir = game_root / "unren-extracted"
    out_dir.mkdir()
    (out_dir / "script.rpyc").write_text("stale content")

    proc = _run_unren("extract", "--force", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    backup = game_root / ".unren" / "backups" / "unren-extracted" / "script.rpyc"
    assert backup.read_text() == "stale content"

    proc = _run_unren("cleanup", "restore", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (out_dir / "script.rpyc").read_text() == "stale content"
    assert not backup.exists()


def test_cleanup_delete_requires_yes(tmp_path: Path) -> None:
    game_root = _build_rpa_game(tmp_path)
    out_dir = game_root / "unren-extracted"
    out_dir.mkdir()
    (out_dir / "script.rpyc").write_text("stale content")
    _run_unren("extract", "--force", str(game_root))

    proc = _run_unren("cleanup", "delete", str(game_root))
    assert proc.returncode != 0
    assert "irreversible" in (proc.stdout + proc.stderr).lower()
    backup = game_root / ".unren" / "backups" / "unren-extracted" / "script.rpyc"
    assert backup.exists()


def test_cleanup_delete_with_yes_removes_backups(tmp_path: Path) -> None:
    game_root = _build_rpa_game(tmp_path)
    out_dir = game_root / "unren-extracted"
    out_dir.mkdir()
    (out_dir / "script.rpyc").write_text("stale content")
    _run_unren("extract", "--force", str(game_root))
    backup = game_root / ".unren" / "backups" / "unren-extracted" / "script.rpyc"
    assert backup.exists()

    proc = _run_unren("cleanup", "delete", "--yes", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not backup.exists()


def test_all_command_runs_every_stage(tmp_path: Path) -> None:
    game_root = _build_patch_game(tmp_path)
    proc = _run_unren("--json", "all", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)
    stages = {s["stage"]: s for s in data["value"]["stages"]}
    assert set(stages) == {
        "extract",
        "decompile",
        "console_enable",
        "devmode_enable",
        "skip_enable",
        "rollback_enable",
        "quicksave_enable",
        "quickmenu_enable",
        "disable_save_sync",
    }
    assert all(s["ok"] or s["skipped"] for s in stages.values())
    assert (game_root / "game" / "unren-console.rpy").is_file()
    assert (game_root / "game" / "unren-debug.rpy").is_file()


def test_all_command_dry_run_writes_nothing(tmp_path: Path) -> None:
    game_root = _build_patch_game(tmp_path)
    proc = _run_unren("--dry-run", "all", str(game_root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not (game_root / "game" / "unren-console.rpy").exists()


def test_all_command_fails_closed_on_non_game_dir(non_game_dir: Path) -> None:
    proc = _run_unren("all", str(non_game_dir))
    assert proc.returncode != 0


# --- Milestone 5 (CLI flags): --language / --no-color / colored output ----


def test_language_flag_forces_german_output(tmp_path: Path) -> None:
    proc = _run_unren("--language", "de", "doctor", str(tmp_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "unren doctor" in proc.stdout
    assert "Spiel gefunden:" in proc.stdout
    assert "Game found:" not in proc.stdout


def test_language_flag_after_subcommand_also_works(tmp_path: Path) -> None:
    # Same bugfix pattern as --json: global flags must work either before or
    # after the subcommand.
    proc = _run_unren("doctor", "--language", "de", str(tmp_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Spiel gefunden:" in proc.stdout


def test_default_language_is_english(tmp_path: Path) -> None:
    proc = _run_unren("doctor", str(tmp_path), env={"LC_LANG": "", "LANG": "", "LC_ALL": "", "UNREN_LANGUAGE": ""})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Game found:" in proc.stdout


def test_language_flag_translates_error_messages() -> None:
    proc_en = _run_unren("detect", "/definitely/does/not/exist/anywhere")
    proc_de = _run_unren("--language", "de", "detect", "/definitely/does/not/exist/anywhere")
    assert proc_en.returncode == 1
    assert proc_de.returncode == 1
    assert "Path not found" in (proc_en.stdout + proc_en.stderr)
    assert "Pfad nicht gefunden" in (proc_de.stdout + proc_de.stderr)


def test_no_color_flag_produces_no_ansi_escapes(tmp_path: Path) -> None:
    proc = _run_unren("--no-color", "doctor", str(tmp_path), env={"FORCE_COLOR": "1"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "\x1b[" not in proc.stdout
    assert "\x1b[" not in proc.stderr


def test_no_color_flag_suppresses_error_ansi_escapes() -> None:
    proc = _run_unren(
        "--no-color", "detect", "/definitely/does/not/exist/anywhere", env={"FORCE_COLOR": "1"}
    )
    assert "\x1b[" not in (proc.stdout + proc.stderr)


def test_colored_output_exists_when_no_color_not_set(tmp_path: Path) -> None:
    # FORCE_COLOR forces Rich to emit ANSI even though stdout is a pipe
    # (not a real TTY) under the test harness. `console enable` output
    # contains a status keyword ("wrote"/"already present") that
    # print_report() highlights, so colored output is guaranteed present.
    game_root = _build_patch_game(tmp_path)
    proc = _run_unren("console", "enable", str(game_root), env={"FORCE_COLOR": "1"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "\x1b[" in proc.stdout


def test_colored_error_output_exists_when_no_color_not_set() -> None:
    proc = _run_unren("detect", "/definitely/does/not/exist/anywhere", env={"FORCE_COLOR": "1"})
    assert "\x1b[" in (proc.stdout + proc.stderr)


def test_no_color_flag_after_subcommand_also_works(tmp_path: Path) -> None:
    proc = _run_unren("doctor", "--no-color", str(tmp_path), env={"FORCE_COLOR": "1"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "\x1b[" not in proc.stdout


# --- Milestone 5: menu vs CLI parity (coverage check) ----------------------


def test_every_interactive_menu_action_has_an_equivalent_direct_cli_command() -> None:
    """Structural parity: every unren.ui.interactive.ACTIONS entry must map
    onto a real `unren [COMMAND]` invocation recognized by the real argparse
    parser this same process uses - the CLI surface can never drift out of
    sync with the menu it's paired with."""
    from unren.cli import build_parser
    from unren.ui import interactive

    parser = build_parser()
    valid_commands = set(parser._subparsers._group_actions[0].choices.keys())  # type: ignore[attr-defined]

    def _ctx() -> interactive.MenuContext:
        answers = iter(["/tmp"] + ["y"] * 6)
        return interactive.MenuContext(no_color=True, input_fn=lambda _prompt: next(answers))

    assert len(interactive.ACTIONS) > 0
    for action in interactive.ACTIONS:
        argv = action.build_argv(_ctx())
        assert argv is not None
        assert argv[0] in valid_commands, f"menu action {action.key!r} has no matching CLI command {argv[0]!r}"
