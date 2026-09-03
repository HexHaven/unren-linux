"""Unit tests for unren.ui.interactive (Milestone 5 scope).

Drives the menu loop with a fake input_fn (no real stdin/terminal) and
verifies: menu display, dispatch to unren.cli.main with the expected argv
for every action, invalid-input handling, and clean quit/EOF behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from unren.ui import interactive


def _ctx(answers: list[str]) -> interactive.MenuContext:
    it = iter(answers)

    def fake_input(_prompt: str) -> str:
        return next(it)

    return interactive.MenuContext(no_color=True, input_fn=fake_input)


def test_menu_prints_all_core_action_labels(capsys: pytest.CaptureFixture[str]) -> None:
    from unren.ui.i18n import t

    ctx = _ctx(["q"])
    interactive.run(ctx=ctx)
    out = capsys.readouterr().out
    for action in interactive.ACTIONS:
        assert t(f"menu.option.{action.key}") in out


def test_quit_returns_0_and_prints_goodbye(capsys: pytest.CaptureFixture[str]) -> None:
    ctx = _ctx(["q"])
    code = interactive.run(ctx=ctx)
    assert code == 0
    assert "goodbye" in capsys.readouterr().out.lower() or "wiedersehen" in capsys.readouterr().out.lower()


def test_eof_on_first_prompt_exits_cleanly() -> None:
    def raising_input(_prompt: str) -> str:
        raise EOFError

    ctx = interactive.MenuContext(no_color=True, input_fn=raising_input)
    code = interactive.run(ctx=ctx)
    assert code == 0


def test_invalid_numeric_choice_reprompts(capsys: pytest.CaptureFixture[str]) -> None:
    ctx = _ctx(["999", "q"])
    interactive.run(ctx=ctx)
    captured = capsys.readouterr()
    assert "invalid" in (captured.out + captured.err).lower()


def test_non_numeric_choice_reprompts(capsys: pytest.CaptureFixture[str]) -> None:
    ctx = _ctx(["xyz", "q"])
    interactive.run(ctx=ctx)
    captured = capsys.readouterr()
    assert "invalid" in (captured.out + captured.err).lower()


def test_detect_action_dispatches_to_cli_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_main(argv: list[str]) -> int:
        calls.append(argv)
        return 0

    monkeypatch.setattr("unren.cli.main", fake_main)
    idx = [a.key for a in interactive.ACTIONS].index("detect") + 1
    ctx = _ctx([str(idx), str(tmp_path), "", "q"])  # select detect, path, press-enter, quit
    code = interactive.run(ctx=ctx)
    assert code == 0
    assert calls == [["detect", str(tmp_path)]]


def test_extract_action_builds_expected_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr("unren.cli.main", lambda argv: calls.append(argv) or 0)

    idx = [a.key for a in interactive.ACTIONS].index("extract") + 1
    # path, in-place=y, force=n, dry-run=y, press-enter, quit
    ctx = _ctx([str(idx), str(tmp_path), "y", "n", "y", "", "q"])
    interactive.run(ctx=ctx)
    assert calls == [["extract", str(tmp_path), "--in-place", "--dry-run"]]


def test_cleanup_delete_declined_confirmation_aborts_without_dispatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr("unren.cli.main", lambda argv: calls.append(argv) or 0)

    idx = [a.key for a in interactive.ACTIONS].index("cleanup_delete") + 1
    # path, dry_run=n, confirm=n (declines) -> aborts, then quit
    ctx = _ctx([str(idx), str(tmp_path), "n", "n", "q"])
    interactive.run(ctx=ctx)
    assert calls == []
    assert "returning" in capsys.readouterr().out.lower() or "menü" in capsys.readouterr().out.lower()


def test_cleanup_delete_confirmed_dispatches_with_yes_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr("unren.cli.main", lambda argv: calls.append(argv) or 0)

    idx = [a.key for a in interactive.ACTIONS].index("cleanup_delete") + 1
    ctx = _ctx([str(idx), str(tmp_path), "n", "y", "", "q"])
    interactive.run(ctx=ctx)
    assert calls == [["cleanup", "delete", str(tmp_path), "--yes"]]


def test_every_action_maps_to_a_real_cli_subcommand() -> None:
    # Structural parity guard: every menu action's argv[0] (or argv[0:2] for
    # patch-toggle/cleanup actions) must be a subcommand the real argparse
    # parser recognizes - i.e. the menu can never drift out of sync with the
    # CLI surface it wraps.
    from unren.cli import build_parser

    parser = build_parser()
    valid_commands = set(parser._subparsers._group_actions[0].choices.keys())  # type: ignore[attr-defined]

    for action in interactive.ACTIONS:
        # Build with a context that answers "y" to every yes/no prompt so we
        # get the argv shape without triggering any destructive-confirmation
        # abort path (cleanup_delete only aborts when the user declines).
        ctx = _ctx(["/tmp"] + ["y"] * 6)
        argv = action.build_argv(ctx)
        assert argv is not None
        assert argv[0] in valid_commands, f"menu action {action.key!r} dispatches unknown command {argv[0]!r}"
