"""Unit tests for unren.actions.decompile_rpyc (planning/execution logic)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from unren.actions import decompile_rpyc
from unren.adapters import unrpyc as unrpyc_adapter
from unren.core.context import PythonRuntime
from unren.core.errors import OutputPathError, RuntimeResolutionError
from unren.detection.renpy import RenPyGeneration
from unren.detection.rpyc import RpycFileInfo, RpycFormat, find_rpyc_files

FIXTURES = Path(__file__).parent.parent / "fixtures" / "rpyc_samples"

SYSTEM_PY3 = PythonRuntime(executable=Path(sys.executable), version=sys.version.split()[0], source="system")


def _make_game(tmp_path: Path) -> Path:
    game_root = tmp_path / "MyGame"
    game_dir = game_root / "game"
    game_dir.mkdir(parents=True)
    return game_root


def _seed_rpyc(game_root: Path, name: str = "options.rpyc", *, source: Path | None = None) -> Path:
    source = source or (FIXTURES / "current8_options.rpyc")
    dest = game_root / "game" / name
    dest.write_bytes(source.read_bytes())
    return dest


# --- resolve_output_root ---------------------------------------------------


def test_default_output_dir_is_sibling_unren_decompiled(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    out = decompile_rpyc.resolve_output_root(game_root=game_root, output=None, in_place=False)
    assert out == game_root / "unren-decompiled"


def test_custom_output_dir(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    custom = tmp_path / "custom_out"
    out = decompile_rpyc.resolve_output_root(game_root=game_root, output=str(custom), in_place=False)
    assert out == custom


def test_in_place_uses_game_dir(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    out = decompile_rpyc.resolve_output_root(
        game_root=game_root, output=None, in_place=True, game_dir=game_root / "game"
    )
    assert out == game_root / "game"


def test_output_and_in_place_mutually_exclusive(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    with pytest.raises(OutputPathError):
        decompile_rpyc.resolve_output_root(game_root=game_root, output="/tmp/x", in_place=True)


# --- select_variant_and_runtime (fail-closed generation/runtime selection) -


def test_select_variant_unknown_generation_raises(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    with pytest.raises(RuntimeResolutionError):
        decompile_rpyc.select_variant_and_runtime(RenPyGeneration.UNKNOWN, game_root=game_root)


def test_select_variant_current_generation_uses_current_variant(tmp_path: Path, monkeypatch) -> None:
    import unren.detection.python as python_detect

    monkeypatch.setattr(python_detect, "resolve_python_runtime", lambda root: SYSTEM_PY3)
    game_root = _make_game(tmp_path)

    variant, runtime = decompile_rpyc.select_variant_and_runtime(
        RenPyGeneration.CURRENT, game_root=game_root
    )
    assert variant is unrpyc_adapter.UnrpycVariant.CURRENT
    assert runtime is SYSTEM_PY3


def test_select_variant_current_generation_no_runtime_raises(tmp_path: Path, monkeypatch) -> None:
    import unren.detection.python as python_detect

    unresolved = PythonRuntime(executable=None, version=None, source="unknown")
    monkeypatch.setattr(python_detect, "resolve_python_runtime", lambda root: unresolved)
    game_root = _make_game(tmp_path)

    with pytest.raises(RuntimeResolutionError):
        decompile_rpyc.select_variant_and_runtime(RenPyGeneration.CURRENT, game_root=game_root)


def test_select_variant_legacy_prefers_python2_when_available(tmp_path: Path, monkeypatch) -> None:
    import unren.detection.python as python_detect

    py2 = PythonRuntime(executable=Path("/usr/bin/python2"), version="2.7.18", source="system")
    monkeypatch.setattr(python_detect, "resolve_python2_runtime", lambda root: py2)
    game_root = _make_game(tmp_path)

    variant, runtime = decompile_rpyc.select_variant_and_runtime(
        RenPyGeneration.LEGACY, game_root=game_root
    )
    assert variant is unrpyc_adapter.UnrpycVariant.LEGACY
    assert runtime is py2


def test_select_variant_legacy_falls_back_to_current_without_python2(tmp_path: Path, monkeypatch) -> None:
    import unren.detection.python as python_detect

    unresolved_py2 = PythonRuntime(executable=None, version=None, source="unknown")
    monkeypatch.setattr(python_detect, "resolve_python2_runtime", lambda root: unresolved_py2)
    monkeypatch.setattr(python_detect, "resolve_python_runtime", lambda root: SYSTEM_PY3)
    game_root = _make_game(tmp_path)

    variant, runtime = decompile_rpyc.select_variant_and_runtime(
        RenPyGeneration.LEGACY, game_root=game_root
    )
    assert variant is unrpyc_adapter.UnrpycVariant.CURRENT
    assert runtime is SYSTEM_PY3


def test_select_variant_legacy_raises_when_nothing_resolves(tmp_path: Path, monkeypatch) -> None:
    import unren.detection.python as python_detect

    unresolved = PythonRuntime(executable=None, version=None, source="unknown")
    monkeypatch.setattr(python_detect, "resolve_python2_runtime", lambda root: unresolved)
    monkeypatch.setattr(python_detect, "resolve_python_runtime", lambda root: unresolved)
    game_root = _make_game(tmp_path)

    with pytest.raises(RuntimeResolutionError):
        decompile_rpyc.select_variant_and_runtime(RenPyGeneration.LEGACY, game_root=game_root)


# --- build_plan / dry-run ----------------------------------------------------


def test_dry_run_plans_but_does_not_write(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    _seed_rpyc(game_root)
    rpyc_files = find_rpyc_files(game_root)

    report = decompile_rpyc.build_plan(
        game_root=game_root,
        game_dir=game_root / "game",
        generation=RenPyGeneration.CURRENT,
        rpyc_files=rpyc_files,
    )
    assert report.dry_run is True
    assert report.total_files == 1
    assert not (game_root / "unren-decompiled").exists()
    assert report.variant == "current"
    assert report.files[0].destination.endswith("options.rpy")


def test_plan_flags_unrecognized_format_as_skipped(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    bad = game_root / "game" / "corrupt.rpyc"
    bad.write_bytes(b"not a real rpyc container")
    rpyc_files = [RpycFileInfo(path=bad, format=RpycFormat.UNKNOWN)]

    report = decompile_rpyc.build_plan(
        game_root=game_root,
        game_dir=game_root / "game",
        generation=RenPyGeneration.CURRENT,
        rpyc_files=rpyc_files,
    )
    assert report.total_files == 1
    assert not report.files[0].ok
    assert "unrecognized RPYC container format" in report.files[0].skipped_reason


# --- execute_plan / real decompilation (uses the vendored 'current' unrpyc) -


@pytest.mark.skipif(sys.version_info < (3, 9), reason="vendored current unrpyc requires 3.9+")
def test_real_decompilation_creates_output_dir_and_rpy_file(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    _seed_rpyc(game_root)
    rpyc_files = find_rpyc_files(game_root)

    report = decompile_rpyc.decompile(
        game_root=game_root,
        game_dir=game_root / "game",
        generation=RenPyGeneration.CURRENT,
        rpyc_files=rpyc_files,
    )
    assert report.dry_run is False
    assert report.decompiled == 1
    assert report.total_failed == 0
    out_file = game_root / "unren-decompiled" / "game" / "options.rpy"
    assert out_file.is_file()
    assert len(out_file.read_text(encoding="utf-8")) > 0
    # original .rpyc must be untouched
    assert (game_root / "game" / "options.rpyc").read_bytes() == (FIXTURES / "current8_options.rpyc").read_bytes()


@pytest.mark.skipif(sys.version_info < (3, 9), reason="vendored current unrpyc requires 3.9+")
def test_real_decompilation_in_place(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    _seed_rpyc(game_root)
    rpyc_files = find_rpyc_files(game_root)

    report = decompile_rpyc.decompile(
        game_root=game_root,
        game_dir=game_root / "game",
        generation=RenPyGeneration.CURRENT,
        in_place=True,
        rpyc_files=rpyc_files,
    )
    assert report.decompiled == 1
    out_file = game_root / "game" / "options.rpy"
    assert out_file.is_file()
    assert not (game_root / "unren-decompiled").exists()


@pytest.mark.skipif(sys.version_info < (3, 9), reason="vendored current unrpyc requires 3.9+")
def test_real_decompilation_legacy_generation_falls_back_and_succeeds(tmp_path: Path, monkeypatch) -> None:
    """LEGACY generation with no Python 2 runtime resolved must still
    successfully decompile via the 'current' unrpyc fallback (verified real
    subprocess run against a genuine Ren'Py 7-era sample)."""
    import unren.detection.python as python_detect

    unresolved_py2 = PythonRuntime(executable=None, version=None, source="unknown")
    monkeypatch.setattr(python_detect, "resolve_python2_runtime", lambda root: unresolved_py2)
    monkeypatch.setattr(python_detect, "resolve_python_runtime", lambda root: SYSTEM_PY3)

    game_root = _make_game(tmp_path)
    _seed_rpyc(game_root, source=FIXTURES / "legacy7_options.rpyc")
    rpyc_files = find_rpyc_files(game_root)

    report = decompile_rpyc.decompile(
        game_root=game_root,
        game_dir=game_root / "game",
        generation=RenPyGeneration.LEGACY,
        rpyc_files=rpyc_files,
    )
    assert report.variant == "current"
    assert report.decompiled == 1
    assert report.total_failed == 0


@pytest.mark.skipif(sys.version_info < (3, 9), reason="vendored current unrpyc requires 3.9+")
def test_overwrite_protection_without_force(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    _seed_rpyc(game_root)
    rpyc_files = find_rpyc_files(game_root)

    out_dir = game_root / "unren-decompiled" / "game"
    out_dir.mkdir(parents=True)
    (out_dir / "options.rpy").write_text("existing content")

    report = decompile_rpyc.decompile(
        game_root=game_root,
        game_dir=game_root / "game",
        generation=RenPyGeneration.CURRENT,
        rpyc_files=rpyc_files,
    )
    assert report.total_failed == 1
    assert "already exist" in report.files[0].skipped_reason
    assert (out_dir / "options.rpy").read_text() == "existing content"


@pytest.mark.skipif(sys.version_info < (3, 9), reason="vendored current unrpyc requires 3.9+")
def test_force_overwrites_and_backs_up(tmp_path: Path) -> None:
    game_root = _make_game(tmp_path)
    _seed_rpyc(game_root)
    rpyc_files = find_rpyc_files(game_root)

    out_dir = game_root / "unren-decompiled" / "game"
    out_dir.mkdir(parents=True)
    (out_dir / "options.rpy").write_text("existing content")

    report = decompile_rpyc.decompile(
        game_root=game_root,
        game_dir=game_root / "game",
        generation=RenPyGeneration.CURRENT,
        force=True,
        rpyc_files=rpyc_files,
    )
    assert report.decompiled == 1
    assert (out_dir / "options.rpy").read_text() != "existing content"
    backup = game_root / ".unren" / "backups" / "unren-decompiled" / "game" / "options.rpy"
    assert backup.read_text() == "existing content"


def test_output_path_exists_as_file_raises(tmp_path: Path, monkeypatch) -> None:
    import unren.detection.python as python_detect

    monkeypatch.setattr(python_detect, "resolve_python_runtime", lambda root: SYSTEM_PY3)
    game_root = _make_game(tmp_path)
    conflicting = game_root / "unren-decompiled"
    conflicting.write_text("i am a file, not a dir")
    _seed_rpyc(game_root)
    rpyc_files = find_rpyc_files(game_root)

    with pytest.raises(OutputPathError):
        decompile_rpyc.build_plan(
            game_root=game_root,
            game_dir=game_root / "game",
            generation=RenPyGeneration.CURRENT,
            rpyc_files=rpyc_files,
        )


@pytest.mark.skipif(sys.version_info < (3, 9), reason="vendored current unrpyc requires 3.9+")
def test_real_decompilation_rpc1_format_is_attempted_not_skipped(tmp_path: Path) -> None:
    """Ren'Py 6-era RPC1 container (no 'RENPY RPC2' header, headerless
    zlib+pickle blob) must be classified as decompilable and handed to
    unrpyc, not refused as an unrecognized format - even though a real
    Ren'Py 6 game fixture wasn't available for vendoring, the container
    *shape* (bare zlib stream) is what `unren.detection.rpyc` keys off, and
    unrpyc's own `read_ast_from_file` has an explicit is_rpyc_v1 branch for
    exactly this layout (confirmed by real subprocess invocation here)."""
    game_root = _make_game(tmp_path)
    _seed_rpyc(game_root, name="script.rpyc", source=FIXTURES / "synthetic_rpc1.rpyc")
    rpyc_files = find_rpyc_files(game_root)
    assert rpyc_files[0].format == RpycFormat.RPC1

    report = decompile_rpyc.decompile(
        game_root=game_root,
        game_dir=game_root / "game",
        generation=RenPyGeneration.CURRENT,
        rpyc_files=rpyc_files,
    )
    # The file was attempted (not skipped as unrecognized): unrpyc runs and
    # produces *an* output file, even though the synthetic payload isn't a
    # real Ren'Py AST so its content is not meaningful beyond "it ran".
    assert report.files[0].skipped_reason is None or "unrecognized" not in (
        report.files[0].skipped_reason or ""
    )
    out_file = game_root / "unren-decompiled" / "game" / "script.rpy"
    assert out_file.is_file()


def test_no_rpyc_files_found_empty_report(tmp_path: Path, monkeypatch) -> None:
    import unren.detection.python as python_detect

    monkeypatch.setattr(python_detect, "resolve_python_runtime", lambda root: SYSTEM_PY3)
    game_root = _make_game(tmp_path)

    report = decompile_rpyc.decompile(
        game_root=game_root,
        game_dir=game_root / "game",
        generation=RenPyGeneration.CURRENT,
        rpyc_files=[],
    )
    assert report.total_files == 0
    assert report.decompiled == 0
