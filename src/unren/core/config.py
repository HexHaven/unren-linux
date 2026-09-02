"""TOML config loading (Bauplan config layer).

Uses stdlib tomllib on Python >=3.11, falls back to the `tomli` backport on
3.10. Schema for Milestone 1 is intentionally small — only what `doctor`/`detect`
can plausibly use (default language and default output format placeholders,
plus a table for future tool paths). This schema is a Sirius-level bounded
design choice, not specified verbatim in the Bauplan; documented as a
deviation for review.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from unren.core.errors import ConfigError

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on 3.10
    import tomli as tomllib  # type: ignore[no-redef]


DEFAULT_CONFIG_FILENAMES = ("unren.toml", ".unren.toml")


@dataclass
class UnrenConfig:
    """In-memory representation of an unren.toml config file.

    Fields map to a `[unren]` table:
        language: str | None
        output_format: "text" | "json"
        no_color: bool
        tools: dict[str, str]  # future adapter tool path overrides (M2+)
    """

    language: str | None = None
    output_format: str = "text"
    no_color: bool = False
    tools: dict = field(default_factory=dict)
    source_path: Path | None = None

    @classmethod
    def default(cls) -> "UnrenConfig":
        return cls()

    @classmethod
    def load(cls, path: Path) -> "UnrenConfig":
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ConfigError(
                f"Could not read config file: {path}", details={"path": str(path)}
            ) from exc
        try:
            data = tomllib.loads(raw.decode("utf-8"))
        except Exception as exc:  # tomllib raises tomllib.TOMLDecodeError
            raise ConfigError(
                f"Malformed TOML config: {path}: {exc}", details={"path": str(path)}
            ) from exc

        table = data.get("unren", data)
        cfg = cls(
            language=table.get("language"),
            output_format=table.get("output_format", "text"),
            no_color=bool(table.get("no_color", False)),
            tools=dict(table.get("tools", {})),
            source_path=path,
        )
        if cfg.output_format not in ("text", "json"):
            raise ConfigError(
                f"Invalid output_format in config: {cfg.output_format!r}",
                details={"path": str(path)},
            )
        return cfg


def find_config(explicit_path: str | None, search_dir: Path) -> Path | None:
    """Resolve config file location: explicit --config path, else search upward."""
    if explicit_path:
        p = Path(explicit_path).expanduser()
        if not p.is_file():
            raise ConfigError(f"Config file not found: {p}", details={"path": str(p)})
        return p
    current = search_dir
    for _ in range(6):
        for name in DEFAULT_CONFIG_FILENAMES:
            candidate = current / name
            if candidate.is_file():
                return candidate
        if current.parent == current:
            break
        current = current.parent
    return None
