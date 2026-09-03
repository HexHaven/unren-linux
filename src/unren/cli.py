"""unren CLI entry point.

Surface per Bauplan §7:

    unren [GLOBAL OPTIONS] COMMAND [OPTIONS]

Milestone 1 implements `detect` and `doctor` fully. Other subcommands
(`extract`, `decompile`, `console`, `devmode`, `all`) are registered but only
print a "not yet implemented" message and exit non-zero - their real logic
is later milestones (M2+). Running with no subcommand at all (bare
`unren /path/to/game`, meant to launch the interactive UI per Bauplan §7)
is also stubbed the same way for this milestone since ui/interactive.py
doesn't exist yet.
"""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

from unren import __version__
from unren.actions import extract_rpa
from unren.core.config import UnrenConfig, find_config
from unren.core.errors import UnrenError
from unren.core.result import Result
from unren.detection import game as game_detect
from unren.detection.archives import ArchiveInfo
from unren.ui import output as ui_output

NOT_YET_IMPLEMENTED = ("decompile", "console", "devmode", "all")


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

    for name in NOT_YET_IMPLEMENTED:
        stub_p = subparsers.add_parser(
            name, help=f"({name}) - not yet implemented in this milestone.", parents=[sub_global_opts]
        )
        stub_p.add_argument("path", nargs="?", default=".")

    return parser


def _load_config(args: argparse.Namespace) -> UnrenConfig:
    try:
        cfg_path = find_config(args.config, Path.cwd())
    except UnrenError:
        return UnrenConfig.default()
    if cfg_path is None:
        return UnrenConfig.default()
    return UnrenConfig.load(cfg_path)


def _emit(args: argparse.Namespace, *, text: str, json_data: dict) -> None:
    if args.json:
        rendered = __import__("json").dumps(json_data, indent=2, sort_keys=False)
    else:
        rendered = text

    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        if not args.quiet:
            print(f"Output written to {args.output}")
        return

    if args.quiet and not args.json:
        return
    print(rendered)


def cmd_detect(args: argparse.Namespace) -> int:
    try:
        ctx = game_detect.detect_game(args.path)
    except UnrenError as exc:
        result: Result = Result.failure(exc)
        if args.json:
            _emit(args, text="", json_data=result.to_dict())
        else:
            ui_output.print_error(exc.message, no_color=args.no_color)
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
            f"unren doctor - {__version__}",
            f"OS:              {os_info['system']} {os_info['release']} ({os_info['machine']})",
            f"Game found:      {'yes' if game_found else 'no'}",
        ]
        if game_summary:
            lines.append(f"Ren'Py version:  {game_summary['renpy_generation']} (major={game_summary['renpy_major']})")
            rt = game_summary["python_runtime"]
            lines.append(f"Python runtime:  {rt['executable']} (source={rt['source']})")
            lines.append(f"Archive formats: {', '.join(game_summary['archive_formats_present']) or 'none'}")
        if detection_error:
            lines.append(f"Detection note:  {detection_error}")
        tools_line = ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in diagnosis["tools"].items())
        lines.append(f"Tools available: {tools_line}")
        _emit(args, text="\n".join(lines), json_data=result.to_dict())

    return 0


def _format_extract_text(report: extract_rpa.ExtractionReport) -> str:
    lines = [
        f"Game root:       {report.game_root}",
        f"Output:          {report.output_root}"
        + (" (in-place)" if report.in_place else ""),
        f"Mode:            {'dry-run (no files written)' if report.dry_run else 'extracted'}",
        f"Archives found:  {report.total_archives}",
    ]
    if not report.archives:
        lines.append("No RPA archives found.")
        return "\n".join(lines)

    for plan in report.archives:
        lines.append(f"\n{plan.archive}  [{plan.format}]")
        if not plan.ok:
            lines.append(f"  skipped: {plan.skipped_reason}")
            continue
        if report.dry_run:
            lines.append(f"  would extract {len(plan.members)} file(s) to {plan.output_dir}")
            if plan.conflicts:
                lines.append(
                    f"  WARNING: {len(plan.conflicts)} destination file(s) already exist "
                    "(would require --force)"
                )
        else:
            lines.append(f"  extracted {plan.extracted}/{len(plan.members)} file(s) to {plan.output_dir}")

    lines.append(
        f"\nTotal: {report.total_extracted_files} file(s) extracted, "
        f"{report.total_failed} archive(s) failed/skipped."
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
            ui_output.print_error(exc.message, no_color=args.no_color)
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
            ui_output.print_error(exc.message, no_color=args.no_color)
        return 1

    result = Result.success(report)
    if args.json:
        print(__import__("json").dumps(result.to_dict(), indent=2, sort_keys=False))
    elif not args.quiet:
        print(_format_extract_text(report))

    if report.total_archives == 0:
        return 0
    return 1 if report.total_failed == report.total_archives else 0


def cmd_stub(args: argparse.Namespace, name: str) -> int:
    message = (
        f"'{name}' is not yet implemented in this milestone (Linux Core Skeleton). "
        "Detection-only (detect/doctor) is available; mutating actions land in later milestones."
    )
    if args.json:
        from unren.core.errors import UnsupportedOperationError

        result: Result = Result.failure(UnsupportedOperationError(message, details={"command": name}))
        _emit(args, text="", json_data=result.to_dict())
    else:
        ui_output.print_error(message, no_color=args.no_color)
    return 3


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        # Bare `unren` / `unren PATH` -> interactive mode is out of scope for
        # this milestone (ui/interactive.py is Milestone 5).
        parser.print_help()
        return 3

    if args.command == "detect":
        return cmd_detect(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "extract":
        return cmd_extract(args)
    if args.command in NOT_YET_IMPLEMENTED:
        return cmd_stub(args, args.command)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
