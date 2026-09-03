"""Output formatting for the CLI (Milestone 1 + Milestone 5 scope).

Kept intentionally small: rich is optional (falls back to plain text if not
installed), and no interactive prompts live here (ui/interactive.py is
Milestone 5's menu loop).

Color handling (Milestone 5)
-----------------------------
- ``no_color=True`` (the CLI's ``--no-color`` flag, or config's ``no_color``)
  ALWAYS wins: every function below falls back to plain ``print()`` with no
  Rich Console involved at all, so no ANSI escape codes can be emitted.
- Otherwise, color is used when stdout/stderr is a real terminal, or when the
  ``FORCE_COLOR`` env var is set (a common CLI convention, useful for tests
  that capture subprocess output and still want to assert colored output
  exists). The ``NO_COLOR`` env var (https://no-color.org) also disables
  color, same as ``--no-color``.
- Dynamic/user-controlled text (error messages, translated strings, path
  names) is NEVER passed through Rich's ``[tag]`` markup parser - only
  fixed, code-controlled strings are. This avoids literal brackets in
  report text (e.g. ``"archive.rpa  [RPA-3.0]"``) being misinterpreted as
  markup tags. Coloring of dynamic report text is done by building a
  ``rich.text.Text`` object directly (``_colorize_report``), which treats
  appended strings as literal content, never as markup.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

try:
    from rich.console import Console
    from rich.text import Text

    _FORCE_TERMINAL = True if os.environ.get("FORCE_COLOR") else None
    _console: "Console | None" = Console(force_terminal=_FORCE_TERMINAL)
    _console_err: "Console | None" = Console(stderr=True, force_terminal=_FORCE_TERMINAL)
except Exception:  # rich not installed - optional dependency
    _console = None
    _console_err = None
    Text = None  # type: ignore[assignment]


def supports_color(no_color: bool) -> bool:
    if no_color:
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


def print_line(message: str, *, quiet: bool = False, no_color: bool = False) -> None:
    if quiet:
        return
    if _console is not None and supports_color(no_color):
        _console.print(message, markup=False, soft_wrap=True)
    else:
        print(message)


def print_error(message: str, *, no_color: bool = False) -> None:
    if _console_err is not None and supports_color(no_color) and Text is not None:
        line = Text("error: ", style="bold red")
        line.append(message)
        _console_err.print(line, soft_wrap=True)
    else:
        print(f"error: {message}", file=sys.stderr)


_STATUS_WORD_RE = re.compile(
    r"\bFAILED\b|\bfailed\b|\bskipped\b"
    r"|\b(?:ok|done|extracted|decompiled|wrote|restored|already present)\b",
    re.IGNORECASE,
)


def _status_style(word: str) -> str:
    lowered = word.lower()
    if lowered == "failed":
        return "bold red"
    if lowered == "skipped":
        return "yellow"
    return "green"


def _colorize_report(text: str) -> Any:
    """Build a Text with known status keywords highlighted.

    Uses ``Text.append`` (literal content, never markup-parsed) so any
    literal ``[...]`` already present in the report text (e.g. format tags
    like ``[RPA-3.0]``) passes through unchanged instead of being
    misinterpreted as a Rich markup tag. Only called when Text is available
    (guarded by callers via ``Text is not None``).
    """
    assert Text is not None
    result = Text()
    pos = 0
    for m in _STATUS_WORD_RE.finditer(text):
        result.append(text[pos : m.start()])
        result.append(m.group(0), style=_status_style(m.group(0)))
        pos = m.end()
    result.append(text[pos:])
    return result


def print_report(text: str, *, quiet: bool = False, no_color: bool = False) -> None:
    """Print a formatted multi-line report, colorizing status keywords when enabled."""
    if quiet:
        return
    if _console is not None and supports_color(no_color) and Text is not None:
        _console.print(_colorize_report(text), soft_wrap=True)
    else:
        print(text)


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, sort_keys=False))


def format_game_context_text(ctx, *, verbose: bool = False) -> str:
    """Human-readable, translated rendering of a GameContext for `unren detect`."""
    from unren.ui.i18n import t

    lines = []
    lines.append(t("cli.detect.root", root=ctx.root))
    lines.append(t("cli.detect.game_found", value=t("cli.value.yes") if ctx.is_game else t("cli.value.no")))
    if ctx.game_dir:
        lines.append(t("cli.detect.game_dir", dir=ctx.game_dir))
    if ctx.renpy_dir:
        lines.append(t("cli.detect.renpy_dir", dir=ctx.renpy_dir))

    gen = ctx.renpy_version.generation
    gen_label = gen.value if hasattr(gen, "value") else str(gen)
    major = ctx.renpy_version.major
    version_str = gen_label + (t("cli.detect.major_suffix", major=major) if major is not None else "")
    lines.append(t("cli.detect.renpy_version", version=version_str))
    if verbose and ctx.renpy_version.method:
        lines.append(t("cli.detect.detected_via", method=ctx.renpy_version.method, raw=ctx.renpy_version.raw))

    rt = ctx.runtime
    if rt.resolved:
        lines.append(t("cli.detect.python_runtime", executable=rt.executable, version=rt.version, source=rt.source))
    else:
        lines.append(t("cli.detect.python_runtime_not_found"))

    if ctx.archives:
        lines.append(t("cli.detect.archives_found", count=len(ctx.archives)))
        for a in ctx.archives:
            lines.append(t("cli.detect.archive_entry", name=a.path.name, format=a.format))
    else:
        lines.append(t("cli.detect.archives_none"))

    return "\n".join(lines)
