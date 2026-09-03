"""Interactive menu loop for unren (Milestone 5).

Launched by `unren.cli.main()` when invoked with no subcommand at all
(bare `unren`). This module is a *pure UI wrapper*: every menu action is
dispatched by building the equivalent `argv` a user would type on the
command line and handing it straight to :func:`unren.cli.main` - the exact
same entry point `unren <command> ...` uses from a shell. No business
logic (detection, extraction, decompilation, patching, ...) is
implemented here; this module never imports `unren.core`, `unren.actions`,
`unren.adapters`, or `unren.detection` directly, only `unren.cli` (lazily,
to avoid a circular import at module load time) and the UI-layer
`unren.ui.output` / `unren.ui.i18n` helpers.

Because every menu action maps 1:1 onto a real `unren.cli` subcommand
invocation, menu/CLI parity is structural rather than something that can
drift: adding a menu entry *is* adding a CLI invocation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from unren.ui import output as ui_output
from unren.ui.i18n import t

# Sentinel returned by an action's argv builder to mean "user aborted /
# declined a confirmation - go back to the menu without dispatching".
_ABORTED = None


@dataclass
class MenuContext:
    """Injectable I/O for the menu loop (real stdin/stdout by default).

    Tests provide a fake `input_fn` (e.g. an iterator of canned answers) to
    drive the loop without a real terminal.
    """

    no_color: bool = False
    input_fn: Callable[[str], str] = field(default=input)


@dataclass
class MenuAction:
    key: str  # matches locale keys menu.option.<key> / menu.description.<key>
    build_argv: Callable[[MenuContext], "list[str] | None"]


class MenuExit(Exception):
    """Raised internally to unwind the loop on quit/EOF/interrupt."""


def _read(ctx: MenuContext, prompt_key: str, **kwargs: str) -> str:
    try:
        return ctx.input_fn(t(prompt_key, **kwargs))
    except EOFError:
        raise MenuExit from None
    except KeyboardInterrupt:
        raise MenuExit from None


def _prompt_path(ctx: MenuContext) -> str:
    raw = _read(ctx, "menu.prompt.game_path", default=".").strip()
    return raw or "."


def _prompt_yes_no(ctx: MenuContext, key: str) -> bool:
    raw = _read(ctx, key).strip().lower()
    return raw in ("y", "yes", "j", "ja")


def _simple(command: str) -> Callable[[MenuContext], "list[str] | None"]:
    """Build an argv builder for a plain `unren <command> PATH` action."""

    def build(ctx: MenuContext) -> "list[str] | None":
        return [command, _prompt_path(ctx)]

    return build


def _patch_enable(name: str) -> Callable[[MenuContext], "list[str] | None"]:
    """Build an argv builder for `unren <name> enable PATH` toggle actions."""

    def build(ctx: MenuContext) -> "list[str] | None":
        return [name, "enable", _prompt_path(ctx)]

    return build


def _build_extract(ctx: MenuContext) -> "list[str] | None":
    argv = ["extract", _prompt_path(ctx)]
    if _prompt_yes_no(ctx, "menu.prompt.in_place"):
        argv.append("--in-place")
    if _prompt_yes_no(ctx, "menu.prompt.force"):
        argv.append("--force")
    if _prompt_yes_no(ctx, "menu.prompt.dry_run"):
        argv.append("--dry-run")
    return argv


def _build_decompile(ctx: MenuContext) -> "list[str] | None":
    argv = ["decompile", _prompt_path(ctx)]
    if _prompt_yes_no(ctx, "menu.prompt.in_place"):
        argv.append("--in-place")
    if _prompt_yes_no(ctx, "menu.prompt.force"):
        argv.append("--force")
    if _prompt_yes_no(ctx, "menu.prompt.try_harder"):
        argv.append("--try-harder")
    if _prompt_yes_no(ctx, "menu.prompt.dry_run"):
        argv.append("--dry-run")
    return argv


def _build_cleanup_restore(ctx: MenuContext) -> "list[str] | None":
    argv = ["cleanup", "restore", _prompt_path(ctx)]
    if _prompt_yes_no(ctx, "menu.prompt.dry_run"):
        argv.append("--dry-run")
    return argv


def _build_cleanup_delete(ctx: MenuContext) -> "list[str] | None":
    path = _prompt_path(ctx)
    dry_run = _prompt_yes_no(ctx, "menu.prompt.dry_run")
    if not dry_run and not _prompt_yes_no(ctx, "menu.prompt.confirm"):
        return _ABORTED
    argv = ["cleanup", "delete", path]
    if dry_run:
        argv.append("--dry-run")
    else:
        argv.append("--yes")
    return argv


def _build_all(ctx: MenuContext) -> "list[str] | None":
    argv = ["all", _prompt_path(ctx)]
    if _prompt_yes_no(ctx, "menu.prompt.force"):
        argv.append("--force")
    if _prompt_yes_no(ctx, "menu.prompt.dry_run"):
        argv.append("--dry-run")
    return argv


# Ordered menu entries. Order here is the order shown/numbered in the menu.
# `quit` is handled separately (always last, via 'q').
ACTIONS: tuple[MenuAction, ...] = (
    MenuAction("detect", _simple("detect")),
    MenuAction("doctor", _simple("doctor")),
    MenuAction("extract", _build_extract),
    MenuAction("decompile", _build_decompile),
    MenuAction("console", _patch_enable("console")),
    MenuAction("devmode", _patch_enable("devmode")),
    MenuAction("skip", _patch_enable("skip")),
    MenuAction("skipall", _patch_enable("skipall")),
    MenuAction("rollback", _patch_enable("rollback")),
    MenuAction("quicksave", _patch_enable("quicksave")),
    MenuAction("quickmenu", _patch_enable("quickmenu")),
    MenuAction("nosync", _patch_enable("nosync")),
    MenuAction("cleanup_restore", _build_cleanup_restore),
    MenuAction("cleanup_delete", _build_cleanup_delete),
    MenuAction("all", _build_all),
)


def _resolve_choice(choice: str) -> "MenuAction | None":
    choice = choice.strip()
    if not choice.isdigit():
        return None
    idx = int(choice)
    if 1 <= idx <= len(ACTIONS):
        return ACTIONS[idx - 1]
    return None


def _print_menu(ctx: MenuContext) -> None:
    ui_output.print_line("", no_color=ctx.no_color)
    ui_output.print_line(t("menu.subtitle"), no_color=ctx.no_color)
    for idx, action in enumerate(ACTIONS, start=1):
        label = t(f"menu.option.{action.key}")
        ui_output.print_line(f"  {idx}) {label}", no_color=ctx.no_color)
    ui_output.print_line(f"  q) {t('menu.option.quit')}", no_color=ctx.no_color)


def _dispatch(argv: list[str]) -> int:
    """Invoke the real CLI entry point with `argv` (no core logic here)."""
    from unren.cli import main as cli_main  # lazy: avoid import cycle with cli.py

    try:
        return cli_main(argv)
    except SystemExit as exc:  # argparse errors, --version/--help, etc.
        code = exc.code
        return code if isinstance(code, int) else 1


def run(*, ctx: "MenuContext | None" = None) -> int:
    """Run the interactive menu loop until the user quits or input ends.

    Returns a process-style exit code (0 on a clean quit).
    """
    ctx = ctx or MenuContext()
    ui_output.print_line(t("menu.title"), no_color=ctx.no_color)

    try:
        while True:
            _print_menu(ctx)
            choice = _read(ctx, "menu.prompt.select_action")
            if choice.strip().lower() in ("q", "quit", "exit"):
                break

            action = _resolve_choice(choice)
            if action is None:
                ui_output.print_error(t("menu.invalid_choice", choice=choice), no_color=ctx.no_color)
                continue

            try:
                argv = action.build_argv(ctx)
            except MenuExit:
                raise
            if argv is None:
                ui_output.print_line(t("menu.returning_to_menu"), no_color=ctx.no_color)
                continue

            _dispatch(argv)

            try:
                _read(ctx, "menu.press_enter")
            except MenuExit:
                raise
    except MenuExit:
        pass

    ui_output.print_line(t("menu.goodbye"), no_color=ctx.no_color)
    return 0
