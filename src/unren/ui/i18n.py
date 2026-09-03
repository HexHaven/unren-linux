"""Translation loading + lookup for the interactive UI and CLI (Milestone 5).

Translation file schema
------------------------
Each locale is a single flat JSON object of ``"dotted.key": "text"`` pairs,
stored at ``src/unren/locales/<lang>.json`` (shipped inside the installed
package, so it works after ``pip install`` regardless of the process cwd).

    {
      "menu.title": "unren - Ren'Py game toolkit",
      "error.path_not_found": "Path not found: {path}"
    }

Conventions for key namespaces (coordinate with the CLI/menu tasks that
consume ``t()``):

    menu.*    -- interactive menu strings (titles, prompts, per-action labels)
    cli.*     -- generic CLI messages (status lines, confirmations)
    error.*   -- error strings, one key per ``UnrenError.code``
                 (dashes replaced with underscores, e.g. ``not-a-game-directory``
                 -> ``error.not_a_game_directory``)

Values may contain ``str.format`` style placeholders (``{path}``, ``{name}``,
...) which are filled in from the ``**kwargs`` passed to :func:`t`.

Every locale file MUST define the same key set as ``en.json`` (enforced by a
coverage test); ``en.json`` is the required fallback and must therefore be
complete by construction.

Language detection order (see :func:`detect_language`):

    1. explicit CLI ``--language`` flag
    2. ``LC_LANG`` (or ``LANG``/``LC_ALL`` as common Unix fallbacks) env var
    3. config file ``language`` setting
    4. default: ``"en"``

Fallback behaviour (see :func:`translate`): a translation key missing from
the selected language falls back to English; a key missing from English too
returns the raw key unchanged. Lookup never raises and never silently
returns an empty string.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

DEFAULT_LANGUAGE = "en"

# Env vars checked, in priority order, for language detection (tier 2).
_LANGUAGE_ENV_VARS = ("UNREN_LANGUAGE", "LC_LANG", "LC_ALL", "LANG")


class TranslationError(Exception):
    """Raised when a locale file exists but is not valid translation data."""


def locales_dir() -> Path:
    """Default directory containing ``<lang>.json`` locale files.

    Lives inside the package (``src/unren/locales/``) rather than the repo
    root so translations are included when the package is installed.
    """
    return Path(__file__).resolve().parent.parent / "locales"


def _normalize_lang_code(raw: str) -> str:
    """Reduce a POSIX locale string to a bare language code.

    ``"de_DE.UTF-8"`` -> ``"de"``, ``"en"`` -> ``"en"``, ``""`` -> ``""``.
    """
    return raw.strip().split(".", 1)[0].split("_", 1)[0].lower()


def detect_language(
    *,
    cli_language: str | None = None,
    env: Mapping[str, str] | None = None,
    config_language: str | None = None,
    default: str = DEFAULT_LANGUAGE,
) -> str:
    """Pure function implementing the language-detection precedence order.

    explicit ``cli_language`` > env var (``UNREN_LANGUAGE``/``LC_LANG``/
    ``LC_ALL``/``LANG``) > ``config_language`` > ``default``.
    """
    if cli_language:
        return _normalize_lang_code(cli_language)

    env_map = env if env is not None else os.environ
    for var in _LANGUAGE_ENV_VARS:
        value = env_map.get(var)
        if value:
            normalized = _normalize_lang_code(value)
            if normalized:
                return normalized

    if config_language:
        return _normalize_lang_code(config_language)

    return default


def load_locale_file(language: str, directory: Path | None = None) -> dict[str, str]:
    """Load a single ``<language>.json`` file. Returns ``{}`` if it's absent.

    Raises :class:`TranslationError` if the file exists but is not a flat
    JSON object of strings (a malformed locale file should be a loud
    startup/test failure, not a silent per-key fallback).
    """
    directory = directory if directory is not None else locales_dir()
    path = directory / f"{language}.json"
    if not path.is_file():
        return {}

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TranslationError(f"Could not read locale file: {path}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TranslationError(f"Malformed JSON in locale file: {path}: {exc}") from exc

    if not isinstance(data, dict) or not all(isinstance(v, str) for v in data.values()):
        raise TranslationError(f"Locale file must be a flat object of string values: {path}")

    return data


def load_translations(directory: Path | None = None) -> dict[str, dict[str, str]]:
    """Load every ``*.json`` locale file in ``directory`` into memory.

    Returns ``{language_code: {key: text}}``. Called once at startup by
    :func:`configure`; callers that only need one language can use
    :func:`load_locale_file` directly.
    """
    directory = directory if directory is not None else locales_dir()
    translations: dict[str, dict[str, str]] = {}
    if not directory.is_dir():
        return translations
    for path in sorted(directory.glob("*.json")):
        translations[path.stem] = load_locale_file(path.stem, directory)
    return translations


def translate(
    key: str,
    language: str,
    translations: Mapping[str, Mapping[str, str]],
    *,
    fallback_language: str = DEFAULT_LANGUAGE,
    **kwargs: Any,
) -> str:
    """Resolve ``key`` for ``language`` with English fallback.

    Resolution order: selected language -> ``fallback_language`` -> the raw
    key itself. Never raises for a missing key. If the resolved string has
    ``str.format`` placeholders that don't match ``kwargs``, the unformatted
    string is returned rather than raising.
    """
    table = translations.get(language) or {}
    raw = table.get(key)

    if raw is None:
        fallback_table = translations.get(fallback_language) or {}
        raw = fallback_table.get(key)

    if raw is None:
        return key

    if not kwargs:
        return raw

    try:
        return raw.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return raw


# --- module-level convenience state ----------------------------------------
#
# `configure()` is meant to be called once from CLI startup (`unren.cli.main`)
# after argument parsing / config loading, so `t()` can be used ergonomically
# everywhere else without threading language/translations through every
# call site. All the logic above this line is pure and independently
# unit-testable without touching this state.

_state: dict[str, object] = {"language": DEFAULT_LANGUAGE, "translations": None}


def configure(
    *,
    cli_language: str | None = None,
    env: Mapping[str, str] | None = None,
    config_language: str | None = None,
    directory: Path | None = None,
) -> str:
    """Detect the active language, load+cache all translations, return the language code."""
    language = detect_language(cli_language=cli_language, env=env, config_language=config_language)
    _state["language"] = language
    _state["translations"] = load_translations(directory)
    return language


def set_language(language: str) -> None:
    """Explicitly override the active language (e.g. in tests)."""
    _state["language"] = language


def current_language() -> str:
    return str(_state["language"])


def t(key: str, **kwargs: Any) -> str:
    """Translate ``key`` into the currently configured language.

    Lazily calls :func:`configure` on first use (with no CLI/config
    overrides) if nothing has configured the module yet, so `t()` is always
    safe to call. Extra ``**kwargs`` fill ``str.format`` placeholders in the
    translated text.
    """
    if _state["translations"] is None:
        configure()
    translations = _state["translations"]
    assert isinstance(translations, dict)
    return translate(key, str(_state["language"]), translations, **kwargs)
