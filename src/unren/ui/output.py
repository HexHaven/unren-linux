"""Minimal output formatting for `detect`/`doctor` (Milestone 1 scope).

Kept intentionally small: rich is optional (falls back to plain text if not
installed), and no interactive prompts live here (ui/interactive.py is
Milestone 5).
"""

from __future__ import annotations

import json
import sys
from typing import Any

try:
    from rich.console import Console

    _console: "Console | None" = Console()
    _console_err: "Console | None" = Console(stderr=True)
except Exception:  # rich not installed - optional dependency
    _console = None
    _console_err = None


def supports_color(no_color: bool) -> bool:
    if no_color:
        return False
    return sys.stdout.isatty()


def print_line(message: str, *, quiet: bool = False, no_color: bool = False) -> None:
    if quiet:
        return
    if _console is not None and supports_color(no_color):
        _console.print(message)
    else:
        print(message)


def print_error(message: str, *, no_color: bool = False) -> None:
    if _console_err is not None and supports_color(no_color):
        _console_err.print(f"[bold red]error:[/bold red] {message}")
    else:
        print(f"error: {message}", file=sys.stderr)


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, sort_keys=False))


def format_game_context_text(ctx, *, verbose: bool = False) -> str:
    """Human-readable rendering of a GameContext for `unren detect`."""
    lines = []
    lines.append(f"Root:            {ctx.root}")
    lines.append(f"Game found:      {'yes' if ctx.is_game else 'no'}")
    if ctx.game_dir:
        lines.append(f"game/ dir:       {ctx.game_dir}")
    if ctx.renpy_dir:
        lines.append(f"renpy/ dir:      {ctx.renpy_dir}")

    gen = ctx.renpy_version.generation
    gen_label = gen.value if hasattr(gen, "value") else str(gen)
    major = ctx.renpy_version.major
    version_str = f"{gen_label}" + (f" (major {major})" if major is not None else "")
    lines.append(f"Ren'Py version:  {version_str}")
    if verbose and ctx.renpy_version.method:
        lines.append(f"  detected via:  {ctx.renpy_version.method} ({ctx.renpy_version.raw})")

    rt = ctx.runtime
    if rt.resolved:
        lines.append(f"Python runtime:  {rt.executable} ({rt.version}, source={rt.source})")
    else:
        lines.append("Python runtime:  not found")

    if ctx.archives:
        lines.append(f"Archives found:  {len(ctx.archives)}")
        for a in ctx.archives:
            lines.append(f"  - {a.path.name}  [{a.format}]")
    else:
        lines.append("Archives found:  none")

    return "\n".join(lines)
