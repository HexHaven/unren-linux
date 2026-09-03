"""unren CLI entry point.

Surface per Bauplan §7:

    unren [GLOBAL OPTIONS] COMMAND [OPTIONS]

Milestone 4 completed the primary action surface: `detect`, `doctor`,
`extract`, `decompile` (M1-M3), plus `console enable`, `devmode enable`,
`skip enable`, `skipall enable`, `rollback enable`, `quicksave enable`,
`quickmenu enable`, `nosync enable` (additive `.rpy` game-config patches -
`unren.actions.enable_console`/`enable_devmode`/`game_patches`), `cleanup
restore`/`cleanup delete` (`unren.actions.cleanup`), and `all` (runs every
non-destructive action in a safe order - `unren.actions.run_all`).

Milestone 5 adds: bare `unren` (no subcommand) launches the interactive
menu (`unren.ui.interactive`); a global `--language <code>` flag that
forces i18n language selection (overriding auto-detection); human-readable,
translated (`unren.ui.i18n.t()`) text for every command's non-JSON output
and every error message; and colored output (via `unren.ui.output`, using
Rich when installed) that's fully suppressed by `--no-color`. Every
interactive menu action has a directly equivalent `unren [COMMAND]`
invocation - the menu module (`unren.ui.interactive`) dispatches straight
into this module's `main()`, so CLI/menu parity is structural.
"""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path
from typing import Any

from unren import __version__
from unren.actions import cleanup as cleanup_action
from unren.actions import decompile_rpyc, enable_console, enable_devmode, extract_rpa, game_patches, run_all
from unren.core.config import UnrenConfig, find_config
from unren.core.errors import UnrenError
from unren.core.result import Result
from unren.detection import game as game_detect
from unren.detection.archives import ArchiveInfo
from unren.detection.rpyc import find_rpyc_files
from unren.ui import i18n
from unren.ui import output as ui_output
from unren.ui.i18n import t


def build_parser() -> argparse.ArgumentParser:
    # Shared "global options". Bugfix (Milestone 1 verification pass): these
    # used to be defined ONLY on the top-level parser, so
    # `unren doctor --json` failed with "unrecognized arguments: --json" -
    # global flags had to precede the subcommand (`unren --json doctor`).
    # That's a genuine usability bug (and violates this project's own
    # acceptance criteria, which specifies `unren doctor --json` as valid
    # usage).
    #
    # Adding the *same* parent parser to both the top-level parser and every
    # subparser is not enough by itself: argparse's subparsers re-apply their
    # own action defaults into the shared namespace during parsing, which
    # silently stomps on values already set by the top-level parser (e.g.
    # `unren --json doctor` would have --json set True by the top-level
    # parser, then immediately reset to False by the doctor subparser's own
    # default). The fix is to give the *subparser* copies of these options
    # argparse.SUPPRESS as their default, so subparsers only ever set an
    # attribute when the flag is actually given after the subcommand,
    # instead of always overwriting it. The top-level copies keep real
    # (False) defaults so `args.json` etc. always exist even if the flag is
    # never passed anywhere.
    def _make_global_opts(*, suppress_defaults: bool) -> argparse.ArgumentParser:
        default = argparse.SUPPRESS if suppress_defaults else False
        p = argparse.ArgumentParser(add_help=False)
        p.add_argument("--dry-run", action="store_true", default=default, help="Do not perform mutating actions.")
        p.add_argument("--verbose", action="store_true", default=default, help="Verbose output.")
        p.add_argument("--quiet", action="store_true", default=default, help="Suppress non-essential output.")
        p.add_argument("--json", action="store_true", default=default, help="Emit machine-readable JSON output.")
        p.add_argument("--no-color", action="store_true", default=default, help="Disable colored output.")
        p.add_argument(
            "--language",
            metavar="CODE",
            default=(argparse.SUPPRESS if suppress_defaults else None),
            help="Force a language (e.g. 'de'), overriding auto-detection.",
        )
        p.add_argument("--output", metavar="PATH", default=(argparse.SUPPRESS if suppress_defaults else None), help="Write output to PATH instead of stdout.")
        p.add_argument("--config", metavar="PATH", default=(argparse.SUPPRESS if suppress_defaults else None), help="Explicit path to a config TOML file.")
        return p

    top_global_opts = _make_global_opts(suppress_defaults=False)
    sub_global_opts = _make_global_opts(suppress_defaults=True)

    parser = argparse.ArgumentParser(
        prog="unren",
        description="Native Linux toolkit for Ren'Py games (GPLv3 port of UnRen-forall).",
        parents=[top_global_opts],
    )
    parser.add_argument("--version", action="version", version=f"unren {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    detect_p = subparsers.add_parser(
        "detect", help="Detect a Ren'Py game and print diagnostics.", parents=[sub_global_opts]
    )
    detect_p.add_argument("path", nargs="?", default=".", help="Path to the game directory.")

    doctor_p = subparsers.add_parser(
        "doctor", help="Run environment/tooling diagnostics.", parents=[sub_global_opts]
    )
    doctor_p.add_argument("path", nargs="?", default=".", help="Path to probe for a game (default: cwd).")

    extract_p = subparsers.add_parser(
        "extract", help="Extract RPA archives from a game.", parents=[sub_global_opts]
    )
    extract_p.add_argument("path", nargs="?", default=".", help="Path to the game directory.")
    extract_p.add_argument(
        "--in-place",
        action="store_true",
        default=False,
        help="Extract into the game's own game/ directory instead of a separate unren-extracted/ folder.",
    )
    extract_p.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite existing destination files (backs them up first under .unren/backups/).",
    )

    decompile_p = subparsers.add_parser(
        "decompile", help="Decompile .rpyc/.rpymc files from a game.", parents=[sub_global_opts]
    )
    decompile_p.add_argument("path", nargs="?", default=".", help="Path to the game directory.")
    decompile_p.add_argument(
        "--in-place",
        action="store_true",
        default=False,
        help="Decompile next to the original .rpyc files instead of a separate unren-decompiled/ folder.",
    )
    decompile_p.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite existing .rpy/.rpym files (backs them up first under .unren/backups/; passes --clobber to unrpyc).",
    )
    decompile_p.add_argument(
        "--try-harder",
        action="store_true",
        default=False,
        help="Pass --try-harder to unrpyc (workarounds for common obfuscation; slower).",
    )

    # --- game-config patch subcommands (console/devmode/skip/rollback/etc.) ---
    # Each is a `unren <name> enable [PATH]` invocation, matching the Bauplan
    # §7 CLI examples (`unren console enable /path/to/game`). All share the
    # same idempotent additive-.rpy-file mechanism (unren.core.game_patch);
    # "enable" is the only verb for this milestone (no "disable" - upstream
    # itself has no undo for these beyond `cleanup restore`, which reverts
    # via the generic backup mechanism, not a per-toggle disable).
    patch_subcommands = (
        ("console", "Enable Ren'Py's built-in developer console + config.developer."),
        ("devmode", "Enable Ren'Py's config.debug developer flag."),
        ("skip", "Enable force-skip of seen dialogue (hold-Ctrl skip)."),
        ("skipall", "Enable force-skip including unseen dialogue and transitions."),
        ("rollback", "Force-enable rollback (undo/scroll-back), even if the game disabled it."),
        ("quicksave", "Bind F5/F9 to QuickSave/QuickLoad regardless of the game's own keymap."),
        ("quickmenu", "Force the quick-menu overlay to always be visible."),
        ("nosync", "Disable Ren'Py's cross-device save-sync (config.has_sync)."),
    )
    for name, help_text in patch_subcommands:
        patch_p = subparsers.add_parser(name, help=help_text, parents=[sub_global_opts])
        patch_sub = patch_p.add_subparsers(dest=f"{name}_action")
        enable_p = patch_sub.add_parser("enable", help=f"Write the {name} marker file.", parents=[sub_global_opts])
        enable_p.add_argument("path", nargs="?", default=".", help="Path to the game directory.")

    # --- cleanup: restore/delete .unren/backups/ --------------------------
    cleanup_p = subparsers.add_parser(
        "cleanup", help="Restore or permanently delete files backed up by other actions.", parents=[sub_global_opts]
    )
    cleanup_sub = cleanup_p.add_subparsers(dest="cleanup_action")

    restore_p = cleanup_sub.add_parser(
        "restore", help="Restore every backed-up file to its original location.", parents=[sub_global_opts]
    )
    restore_p.add_argument("path", nargs="?", default=".", help="Path to the game directory.")

    delete_p = cleanup_sub.add_parser(
        "delete", help="Permanently delete all backups (irreversible).", parents=[sub_global_opts]
    )
    delete_p.add_argument("path", nargs="?", default=".", help="Path to the game directory.")
    delete_p.add_argument(
        "--yes", action="store_true", default=False, help="Confirm the irreversible deletion (required unless --dry-run)."
    )

    # --- all: run every non-destructive action in a safe order -------------
    all_p = subparsers.add_parser(
        "all", help="Run every relevant non-destructive action sequentially.", parents=[sub_global_opts]
    )
    all_p.add_argument("path", nargs="?", default=".", help="Path to the game directory.")
    all_p.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite existing destination files where applicable (backs them up first).",
    )

    return parser


def _load_config(args: argparse.Namespace) -> UnrenConfig:
    try:
        cfg_path = find_config(args.config, Path.cwd())
    except UnrenError:
        return UnrenConfig.default()
    if cfg_path is None:
        return UnrenConfig.default()
    return UnrenConfig.load(cfg_path)


def _configure_language(args: argparse.Namespace, cfg: UnrenConfig) -> str:
    """Resolve + activate the active language for this invocation.

    Precedence (see unren.ui.i18n.detect_language): explicit `--language`
    CLI flag > env var > config file `language` setting > default `en`.
    Called once from `main()` after config loading, before any command
    dispatch, so every `t()` call for the rest of the process uses the
    resolved language.
    """
    return i18n.configure(cli_language=getattr(args, "language", None), config_language=cfg.language)


def _no_color(args: argparse.Namespace, cfg: UnrenConfig) -> bool:
    """Resolve the effective --no-color state: CLI flag OR config setting."""
    return bool(getattr(args, "no_color", False)) or cfg.no_color


def _translate_error(exc: UnrenError) -> str:
    """Map an UnrenError to its translated `error.<code>` message.

    `exc.code` uses dashes (e.g. "not-a-game-directory"); locale keys use
    underscores (`error.not_a_game_directory`) per the docs/I18N.md
    convention. Falls back to the generic `error.unren_error` key for any
    error code that doesn't have its own dedicated translation key.
    """
    key = "error." + exc.code.replace("-", "_")
    text = t(key, message=exc.message)
    if text == key:  # translate() returns the raw key when nothing matched
        text = t("error.unren_error", message=exc.message)
    return text


def _print_translated_error(exc: UnrenError, *, no_color: bool) -> None:
    ui_output.print_error(_translate_error(exc), no_color=no_color)


def _emit(args: argparse.Namespace, *, text: str, json_data: dict) -> None:
    if args.json:
        rendered = __import__("json").dumps(json_data, indent=2, sort_keys=False)
    else:
        rendered = text

    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        if not args.quiet:
            ui_output.print_line(t("cli.output_written", path=args.output), no_color=args.no_color)
        return

    if args.quiet and not args.json:
        return
    if args.json:
        print(rendered)
    else:
        ui_output.print_report(rendered, no_color=args.no_color)


def cmd_detect(args: argparse.Namespace) -> int:
    try:
        ctx = game_detect.detect_game(args.path)
    except UnrenError as exc:
        result: Result = Result.failure(exc)
        if args.json:
            _emit(args, text="", json_data=result.to_dict())
        else:
            _print_translated_error(exc, no_color=args.no_color)
        return 1

    result = Result.success(ctx)
    text = ui_output.format_game_context_text(ctx, verbose=args.verbose)
    _emit(args, text=text, json_data=result.to_dict())
    return 0 if ctx.is_game else 2


def _tool_availability() -> dict:
    import shutil as _shutil

    tools = ("7z", "p7zip", "git")
    return {tool: _shutil.which(tool) is not None for tool in tools}


def cmd_doctor(args: argparse.Namespace) -> int:
    os_info = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python_impl_version": platform.python_version(),
    }

    game_found = False
    game_summary: dict = {}
    detection_error: str | None = None
    try:
        ctx = game_detect.detect_game(args.path)
        game_found = ctx.is_game
        game_summary = {
            "root": str(ctx.root),
            "is_game": ctx.is_game,
            "game_dir": str(ctx.game_dir) if ctx.game_dir else None,
            "renpy_dir": str(ctx.renpy_dir) if ctx.renpy_dir else None,
            "renpy_generation": ctx.renpy_version.generation.value,
            "renpy_major": ctx.renpy_version.major,
            "renpy_detection_method": ctx.renpy_version.method,
            "python_runtime": {
                "executable": str(ctx.runtime.executable) if ctx.runtime.executable else None,
                "version": ctx.runtime.version,
                "source": ctx.runtime.source,
            },
            "archive_formats_present": sorted({a.format for a in ctx.archives}),
            "archive_count": len(ctx.archives),
        }
    except UnrenError as exc:
        detection_error = exc.message

    diagnosis = {
        "unren_version": __version__,
        "os": os_info,
        "game": game_summary if game_found or game_summary else None,
        "game_found": game_found,
        "detection_error": detection_error,
        "tools": _tool_availability(),
        "config_loaded_from": None,
    }

    try:
        cfg = _load_config(args)
        diagnosis["config_loaded_from"] = str(cfg.source_path) if cfg.source_path else None
    except UnrenError as exc:
        diagnosis["config_error"] = exc.message

    result = Result.success(diagnosis)

    if args.json:
        _emit(args, text="", json_data=result.to_dict())
    else:
        lines = [
            t("cli.doctor.header", version=__version__),
            t(
                "cli.doctor.os",
                system=os_info["system"],
                release=os_info["release"],
                machine=os_info["machine"],
            ),
            t("cli.doctor.game_found", value=t("cli.value.yes") if game_found else t("cli.value.no")),
        ]
        if game_summary:
            lines.append(
                t(
                    "cli.doctor.renpy_version",
                    generation=game_summary["renpy_generation"],
                    major=game_summary["renpy_major"],
                )
            )
            rt = game_summary["python_runtime"]
            lines.append(t("cli.doctor.python_runtime", executable=rt["executable"], source=rt["source"]))
            lines.append(
                t(
                    "cli.doctor.archive_formats",
                    formats=", ".join(game_summary["archive_formats_present"]) or t("cli.value.none"),
                )
            )
        if detection_error:
            lines.append(t("cli.doctor.detection_note", message=detection_error))
        tools_line = ", ".join(
            f"{k}={t('cli.value.yes') if v else t('cli.value.no')}" for k, v in diagnosis["tools"].items()
        )
        lines.append(t("cli.doctor.tools_available", tools=tools_line))
        _emit(args, text="\n".join(lines), json_data=result.to_dict())

    return 0


def _format_extract_text(report: extract_rpa.ExtractionReport) -> str:
    lines = [
        t("cli.extract.game_root", root=report.game_root),
        t("cli.extract.output", output=str(report.output_root) + (t("cli.extract.in_place_suffix") if report.in_place else "")),
        t(
            "cli.extract.mode",
            mode=t("cli.extract.mode.dry_run") if report.dry_run else t("cli.extract.mode.executed"),
        ),
        t("cli.extract.archives_found", count=report.total_archives),
    ]
    if not report.archives:
        lines.append(t("cli.extract.no_archives"))
        return "\n".join(lines)

    for plan in report.archives:
        lines.append("\n" + t("cli.extract.archive_entry", archive=plan.archive, format=plan.format))
        if not plan.ok:
            lines.append(t("cli.extract.skipped", reason=plan.skipped_reason))
            continue
        if report.dry_run:
            lines.append(t("cli.extract.would_extract", count=len(plan.members), output_dir=plan.output_dir))
            if plan.conflicts:
                lines.append(t("cli.extract.conflict_warning", count=len(plan.conflicts)))
        else:
            lines.append(
                t("cli.extract.extracted", extracted=plan.extracted, total=len(plan.members), output_dir=plan.output_dir)
            )

    lines.append(
        "\n" + t("cli.extract.total", extracted=report.total_extracted_files, failed=report.total_failed)
    )
    return "\n".join(lines)


def cmd_extract(args: argparse.Namespace) -> int:
    try:
        ctx = game_detect.detect_game(args.path)
    except UnrenError as exc:
        result: Result = Result.failure(exc)
        if args.json:
            _emit(args, text="", json_data=result.to_dict())
        else:
            _print_translated_error(exc, no_color=args.no_color)
        return 1

    # NOTE: for `extract`, --output means "extraction destination directory"
    # per this milestone's acceptance criteria (`unren extract --output
    # /tmp/out /game` uses /tmp/out), which shadows the *global* --output
    # flag's usual meaning ("write report text to this file instead of
    # stdout", see _emit()). This is a deliberate, scoped reinterpretation of
    # the flag for this one subcommand - documented here since it deviates
    # from the shared global-options contract. Report text/JSON is therefore
    # always printed to stdout for `extract`, never redirected to a file.
    try:
        report = extract_rpa.extract(
            game_root=ctx.root,
            game_dir=ctx.game_dir,
            output=args.output,
            in_place=args.in_place,
            dry_run=args.dry_run,
            force=args.force,
            archives=[
                ArchiveInfo(path=a.path, extension=a.extension, format=a.format)
                for a in ctx.archives
            ],
        )
    except UnrenError as exc:
        result = Result.failure(exc)
        if args.json:
            print(__import__("json").dumps(result.to_dict(), indent=2))
        else:
            _print_translated_error(exc, no_color=args.no_color)
        return 1

    result = Result.success(report)
    if args.json:
        print(__import__("json").dumps(result.to_dict(), indent=2, sort_keys=False))
    elif not args.quiet:
        ui_output.print_report(_format_extract_text(report), no_color=args.no_color)

    if report.total_archives == 0:
        return 0
    return 1 if report.total_failed == report.total_archives else 0


def _format_decompile_text(report: decompile_rpyc.DecompileReport) -> str:
    lines = [
        t("cli.decompile.game_root", root=report.game_root),
        t(
            "cli.decompile.output",
            output=str(report.output_root) + (t("cli.decompile.in_place_suffix") if report.in_place else ""),
        ),
        t(
            "cli.decompile.mode",
            mode=t("cli.decompile.mode.dry_run") if report.dry_run else t("cli.decompile.mode.executed"),
        ),
        t("cli.decompile.variant", variant=report.variant or t("cli.decompile.variant.unresolved")),
        t(
            "cli.decompile.runtime",
            executable=report.runtime_executable or t("cli.decompile.runtime.none"),
            source=report.runtime_source,
        ),
        t("cli.decompile.files_found", count=report.total_files),
    ]
    if not report.files:
        lines.append(t("cli.decompile.no_files"))
        return "\n".join(lines)

    for plan in report.files:
        lines.append("\n" + t("cli.decompile.file_entry", source=plan.source, format=plan.rpyc_format))
        if not plan.ok:
            lines.append(t("cli.decompile.skipped", reason=plan.skipped_reason))
            continue
        if report.dry_run:
            lines.append(t("cli.decompile.would_decompile", destination=plan.destination))
        else:
            lines.append(
                t("cli.decompile.decompiled", destination=plan.destination)
                if plan.exists
                else t("cli.decompile.failed")
            )

    lines.append(
        "\n" + t("cli.decompile.total", decompiled=report.decompiled, failed=report.total_failed)
    )
    return "\n".join(lines)


def cmd_decompile(args: argparse.Namespace) -> int:
    try:
        ctx = game_detect.detect_game(args.path)
    except UnrenError as exc:
        result: Result = Result.failure(exc)
        if args.json:
            _emit(args, text="", json_data=result.to_dict())
        else:
            _print_translated_error(exc, no_color=args.no_color)
        return 1

    try:
        report = decompile_rpyc.decompile(
            game_root=ctx.root,
            game_dir=ctx.game_dir,
            generation=ctx.renpy_version.generation,
            output=args.output,
            in_place=args.in_place,
            dry_run=args.dry_run,
            force=args.force,
            try_harder=args.try_harder,
            rpyc_files=find_rpyc_files(ctx.root),
        )
    except UnrenError as exc:
        result = Result.failure(exc)
        if args.json:
            print(__import__("json").dumps(result.to_dict(), indent=2))
        else:
            _print_translated_error(exc, no_color=args.no_color)
        return 1

    result = Result.success(report)
    if args.json:
        print(__import__("json").dumps(result.to_dict(), indent=2, sort_keys=False))
    elif not args.quiet:
        ui_output.print_report(_format_decompile_text(report), no_color=args.no_color)

    if report.total_files == 0:
        return 0
    return 1 if report.total_failed == report.total_files else 0


PATCH_ACTIONS: dict[str, tuple[str, Any]] = {
    "console": ("cli.patch.label.console", None),  # handled specially (enable_console module)
    "devmode": ("cli.patch.label.devmode", None),  # handled specially (enable_devmode module)
    "skip": ("cli.patch.label.skip", game_patches.enable_skip),
    "skipall": ("cli.patch.label.skipall", game_patches.enable_skip_all),
    "rollback": ("cli.patch.label.rollback", game_patches.enable_rollback),
    "quicksave": ("cli.patch.label.quicksave", game_patches.enable_quicksave),
    "quickmenu": ("cli.patch.label.quickmenu", game_patches.enable_quickmenu),
    "nosync": ("cli.patch.label.nosync", game_patches.disable_save_sync),
}


def _format_patch_text(label_key: str, patch) -> str:
    label = t(label_key)
    if patch.already_present:
        status = t("cli.patch.status.already_present")
    elif patch.dry_run:
        status = t("cli.patch.status.would_write", target=patch.target)
    else:
        status = t("cli.patch.status.wrote", target=patch.target)
    return t("cli.patch.line", label=label, status=status)


def cmd_patch_action(args: argparse.Namespace, name: str) -> int:
    action = getattr(args, f"{name}_action", None)
    if action != "enable":
        ui_output.print_error(t("cli.patch.requires_subaction", name=name), no_color=args.no_color)
        return 2

    try:
        ctx = game_detect.detect_game(args.path)
    except UnrenError as exc:
        result: Result = Result.failure(exc)
        if args.json:
            _emit(args, text="", json_data=result.to_dict())
        else:
            _print_translated_error(exc, no_color=args.no_color)
        return 1

    if ctx.game_dir is None:
        from unren.core.errors import MissingGameDirectoryError

        exc = MissingGameDirectoryError(
            f"No game/ directory found under: {ctx.root}", details={"root": str(ctx.root)}
        )
        result = Result.failure(exc)
        if args.json:
            _emit(args, text="", json_data=result.to_dict())
        else:
            _print_translated_error(exc, no_color=args.no_color)
        return 1

    label_key, fn = PATCH_ACTIONS[name]
    try:
        if name == "console":
            report = enable_console.enable(game_dir=ctx.game_dir, dry_run=args.dry_run)
            patch = report.patch
        elif name == "devmode":
            report = enable_devmode.enable(game_dir=ctx.game_dir, dry_run=args.dry_run)
            patch = report.patch
        else:
            patch = fn(game_dir=ctx.game_dir, dry_run=args.dry_run)
    except UnrenError as exc:
        result = Result.failure(exc)
        if args.json:
            _emit(args, text="", json_data=result.to_dict())
        else:
            _print_translated_error(exc, no_color=args.no_color)
        return 1

    result = Result.success(patch)
    if args.json:
        _emit(args, text="", json_data=result.to_dict())
    elif not args.quiet:
        ui_output.print_report(_format_patch_text(label_key, patch), no_color=args.no_color)
    return 0


def _format_cleanup_text(report) -> str:
    lines = [
        t("cli.cleanup.game_root", root=report.game_root),
        t("cli.cleanup.operation", operation=report.operation),
        t(
            "cli.cleanup.mode",
            mode=t("cli.cleanup.mode.dry_run") if report.dry_run else t("cli.cleanup.mode.executed"),
        ),
        t("cli.cleanup.files", count=report.total_files),
    ]
    if not report.files:
        lines.append(t("cli.cleanup.nothing"))
        return "\n".join(lines)
    for f in report.files:
        verb = t("cli.cleanup.status.restored") if report.operation == "restore" else t("cli.cleanup.status.deleted")
        if report.dry_run:
            verb = t("cli.cleanup.status.would_be", verb=verb)
        status = verb if f.ok else t("cli.cleanup.status.failed", error=f.error)
        lines.append(t("cli.cleanup.entry", backup_path=f.backup_path, status=status))
    lines.append(
        "\n" + t("cli.cleanup.total", succeeded=report.total_succeeded, failed=report.total_failed)
    )
    return "\n".join(lines)


def cmd_cleanup(args: argparse.Namespace) -> int:
    action = getattr(args, "cleanup_action", None)
    if action not in ("restore", "delete"):
        ui_output.print_error(t("cli.cleanup.requires_subaction"), no_color=args.no_color)
        return 2

    try:
        ctx = game_detect.detect_game(args.path)
    except UnrenError as exc:
        result: Result = Result.failure(exc)
        if args.json:
            _emit(args, text="", json_data=result.to_dict())
        else:
            _print_translated_error(exc, no_color=args.no_color)
        return 1

    try:
        if action == "restore":
            report = cleanup_action.restore_backups(game_root=ctx.root, dry_run=args.dry_run)
        else:
            report = cleanup_action.delete_backups(
                game_root=ctx.root, dry_run=args.dry_run, confirm=getattr(args, "yes", False)
            )
    except UnrenError as exc:
        result = Result.failure(exc)
        if args.json:
            _emit(args, text="", json_data=result.to_dict())
        else:
            _print_translated_error(exc, no_color=args.no_color)
        return 1

    result = Result.success(report)
    if args.json:
        _emit(args, text="", json_data=result.to_dict())
    elif not args.quiet:
        ui_output.print_report(_format_cleanup_text(report), no_color=args.no_color)

    if report.total_files == 0:
        return 0
    return 1 if report.total_failed == report.total_files else 0


def _format_all_text(report) -> str:
    lines = [
        t("cli.all.game_root", root=report.game_root),
        t("cli.all.mode", mode=t("cli.all.mode.dry_run") if report.dry_run else t("cli.all.mode.executed")),
        "",
    ]
    for stage in report.stages:
        if stage.skipped:
            lines.append(t("cli.all.stage_skipped", stage=stage.stage, reason=stage.reason))
        elif stage.ok:
            lines.append(t("cli.all.stage_ok", stage=stage.stage))
        else:
            lines.append(t("cli.all.stage_failed", stage=stage.stage, reason=stage.reason))
    lines.append("\n" + t("cli.all.total", ok=report.total_ok, failed=report.total_failed))
    return "\n".join(lines)


def cmd_all(args: argparse.Namespace) -> int:
    try:
        ctx = game_detect.require_game(args.path)
    except UnrenError as exc:
        result: Result = Result.failure(exc)
        if args.json:
            _emit(args, text="", json_data=result.to_dict())
        else:
            _print_translated_error(exc, no_color=args.no_color)
        return 1

    report = run_all.run_all(ctx=ctx, dry_run=args.dry_run, force=args.force)

    result = Result.success(report)
    if args.json:
        _emit(args, text="", json_data=result.to_dict())
    elif not args.quiet:
        ui_output.print_report(_format_all_text(report), no_color=args.no_color)

    return 1 if report.total_failed > 0 else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    cfg = _load_config(args)
    _configure_language(args, cfg)
    args.no_color = _no_color(args, cfg)

    if args.command is None:
        # Bare `unren` (no subcommand) launches the interactive menu
        # (Milestone 5, Bauplan §7) - but only after `launch()` checks
        # whether the cwd itself looks like a Ren'Py game; see
        # unren.ui.interactive.launch() for the full three-case contract
        # (this cwd-auto-detect follow-up task). Lazily imported to avoid
        # a circular import at module load time: ui/interactive.py
        # dispatches menu actions by calling back into this module's
        # `main()`.
        from unren.ui.interactive import launch as launch_interactive

        return launch_interactive()

    try:
        if args.command == "detect":
            return cmd_detect(args)
        if args.command == "doctor":
            return cmd_doctor(args)
        if args.command == "extract":
            return cmd_extract(args)
        if args.command == "decompile":
            return cmd_decompile(args)
        if args.command in PATCH_ACTIONS:
            return cmd_patch_action(args, args.command)
        if args.command == "cleanup":
            return cmd_cleanup(args)
        if args.command == "all":
            return cmd_all(args)
    except OSError as exc:
        # Milestone 7 (Release Candidate) fix: filesystem-level failures that
        # aren't already wrapped as a UnrenError (e.g. PermissionError from a
        # read-only filesystem/mount, or any other OSError raised deep inside
        # an action while writing/creating files) used to propagate as a raw,
        # unhandled Python traceback - a silent-fail/crash, violating this
        # project's own "deterministic error behavior, never a crash" bar
        # (docs acceptance criteria). Convert it into the same structured
        # error contract (text/--json, translated, exit code 1) every other
        # error already uses, instead of letting it escape as a traceback.
        wrapped = UnrenError(
            f"Unexpected filesystem error: {exc.strerror or exc}",
            details={"errno": exc.errno, "filename": exc.filename},
        )
        wrapped.code = "filesystem-error"
        result: Result = Result.failure(wrapped)
        if getattr(args, "json", False):
            _emit(args, text="", json_data=result.to_dict())
        else:
            _print_translated_error(wrapped, no_color=getattr(args, "no_color", False))
        return 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
