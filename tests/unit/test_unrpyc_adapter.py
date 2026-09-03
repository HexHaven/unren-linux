"""Unit tests for unren.adapters.unrpyc (vendored unrpyc subprocess adapter)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from unren.adapters import unrpyc
from unren.core.context import PythonRuntime

FIXTURES = Path(__file__).parent.parent / "fixtures" / "rpyc_samples"


def test_vendor_dirs_exist_for_both_variants() -> None:
    legacy_dir = unrpyc.vendor_dir(unrpyc.UnrpycVariant.LEGACY)
    current_dir = unrpyc.vendor_dir(unrpyc.UnrpycVariant.CURRENT)
    assert legacy_dir.is_dir()
    assert current_dir.is_dir()
    assert (legacy_dir / "unrpyc.py").is_file()
    assert (current_dir / "unrpyc.py").is_file()


def test_vendor_entrypoint_current_reports_v203() -> None:
    text = unrpyc.vendor_entrypoint(unrpyc.UnrpycVariant.CURRENT).read_text(encoding="utf-8")
    assert "__version__ = 'v2.0.3'" in text


def test_vendor_entrypoint_legacy_reports_v132() -> None:
    text = unrpyc.vendor_entrypoint(unrpyc.UnrpycVariant.LEGACY).read_text(encoding="utf-8")
    assert "__version__ = 'v1.3.2'" in text


def test_build_command_raises_without_resolved_runtime() -> None:
    runtime = PythonRuntime(executable=None, version=None, source="unknown")
    with pytest.raises(unrpyc.UnrpycRuntimeError):
        unrpyc.build_command(unrpyc.UnrpycVariant.CURRENT, runtime, [Path("a.rpyc")])


def test_build_command_raises_on_empty_file_list() -> None:
    runtime = PythonRuntime(executable=Path(sys.executable), version="3.14.0", source="system")
    with pytest.raises(unrpyc.UnrpycError):
        unrpyc.build_command(unrpyc.UnrpycVariant.CURRENT, runtime, [])


def test_build_command_shape() -> None:
    runtime = PythonRuntime(executable=Path(sys.executable), version="3.14.0", source="system")
    cmd = unrpyc.build_command(
        unrpyc.UnrpycVariant.CURRENT, runtime, [Path("a.rpyc"), Path("b.rpyc")],
        clobber=True, try_harder=True,
    )
    assert cmd[0] == sys.executable
    assert cmd[1] == str(unrpyc.vendor_entrypoint(unrpyc.UnrpycVariant.CURRENT))
    assert "--clobber" in cmd
    assert "--try-harder" in cmd
    assert cmd[-2:] == ["a.rpyc", "b.rpyc"]


def test_build_command_without_flags_omits_them() -> None:
    runtime = PythonRuntime(executable=Path(sys.executable), version="3.14.0", source="system")
    cmd = unrpyc.build_command(unrpyc.UnrpycVariant.CURRENT, runtime, [Path("a.rpyc")])
    assert "--clobber" not in cmd
    assert "--try-harder" not in cmd


@pytest.mark.skipif(sys.version_info < (3, 9), reason="vendored current unrpyc requires 3.9+")
def test_run_decompile_current_variant_real_subprocess(tmp_path: Path) -> None:
    """End-to-end: really invoke the vendored 'current' unrpyc against a real
    Ren'Py 8-era .rpyc sample and confirm the .rpy file materializes with
    plausible decompiled content. This is the load-bearing verification that
    the vendored copy actually works standalone (not just that our wrapper
    code shells out correctly)."""
    sample = tmp_path / "options.rpyc"
    sample.write_bytes((FIXTURES / "current8_options.rpyc").read_bytes())

    runtime = PythonRuntime(executable=Path(sys.executable), version=sys.version.split()[0], source="system")
    result = unrpyc.run_decompile(unrpyc.UnrpycVariant.CURRENT, runtime, [sample])

    assert result.returncode == 0, result.stderr or result.stdout
    out_file = sample.with_suffix(".rpy")
    assert out_file.is_file()
    content = out_file.read_text(encoding="utf-8")
    assert len(content) > 0


@pytest.mark.skipif(sys.version_info < (3, 9), reason="vendored current unrpyc requires 3.9+")
def test_run_decompile_current_variant_handles_legacy_rpc2_sample(tmp_path: Path) -> None:
    """Verified fallback path: the 'current' (py3.9+) unrpyc can also
    successfully decompile a real Ren'Py 7-era RPC2 sample (with only an
    informational compatibility warning, not a hard failure) - this is what
    unren.actions.decompile_rpyc relies on when no Python 2 runtime is
    available for the 'legacy' variant."""
    sample = tmp_path / "legacy_options.rpyc"
    sample.write_bytes((FIXTURES / "legacy7_options.rpyc").read_bytes())

    runtime = PythonRuntime(executable=Path(sys.executable), version=sys.version.split()[0], source="system")
    result = unrpyc.run_decompile(unrpyc.UnrpycVariant.CURRENT, runtime, [sample])

    assert result.returncode == 0, result.stderr or result.stdout
    out_file = sample.with_suffix(".rpy")
    assert out_file.is_file()


def test_run_decompile_invocation_error_for_nonexistent_executable(tmp_path: Path) -> None:
    sample = tmp_path / "x.rpyc"
    sample.write_bytes(b"irrelevant")
    runtime = PythonRuntime(
        executable=Path("/definitely/does/not/exist/python-xyz"), version="3.99.0", source="system"
    )
    with pytest.raises(unrpyc.UnrpycInvocationError):
        unrpyc.run_decompile(unrpyc.UnrpycVariant.CURRENT, runtime, [sample])
