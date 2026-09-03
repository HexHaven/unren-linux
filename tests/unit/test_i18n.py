"""Unit tests for unren.ui.i18n (Milestone 5 scope).

Covers: language detection precedence, locale-file loading/validation,
missing-key fallback (selected language -> English -> raw key), and
de/en translation-file coverage (identical key sets).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from unren.ui import i18n


# --- detect_language: precedence order --------------------------------------


def test_detect_language_cli_flag_wins_over_everything():
    lang = i18n.detect_language(
        cli_language="de",
        env={"LC_LANG": "fr_FR.UTF-8"},
        config_language="es",
    )
    assert lang == "de"


def test_detect_language_env_var_wins_over_config():
    lang = i18n.detect_language(cli_language=None, env={"LC_LANG": "de_DE.UTF-8"}, config_language="es")
    assert lang == "de"


def test_detect_language_checks_lang_and_lc_all_fallback_vars():
    assert i18n.detect_language(env={"LANG": "de_DE.UTF-8"}) == "de"
    assert i18n.detect_language(env={"LC_ALL": "de_DE.UTF-8"}) == "de"


def test_detect_language_config_used_when_no_cli_or_env():
    lang = i18n.detect_language(cli_language=None, env={}, config_language="de")
    assert lang == "de"


def test_detect_language_defaults_to_en():
    lang = i18n.detect_language(cli_language=None, env={}, config_language=None)
    assert lang == "en"


def test_detect_language_normalizes_posix_locale_codes():
    assert i18n.detect_language(cli_language="de_DE.UTF-8") == "de"
    assert i18n.detect_language(env={"LC_LANG": "EN_US.UTF-8"}) == "en"


def test_detect_language_ignores_empty_env_value():
    lang = i18n.detect_language(cli_language=None, env={"LC_LANG": ""}, config_language="de")
    assert lang == "de"


# --- load_locale_file / load_translations -----------------------------------


def test_load_locale_file_missing_file_returns_empty_dict(tmp_path: Path):
    assert i18n.load_locale_file("xx", tmp_path) == {}


def test_load_locale_file_loads_flat_json(tmp_path: Path):
    (tmp_path / "en.json").write_text(json.dumps({"a.b": "hello"}), encoding="utf-8")
    assert i18n.load_locale_file("en", tmp_path) == {"a.b": "hello"}


def test_load_locale_file_rejects_malformed_json(tmp_path: Path):
    (tmp_path / "en.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(i18n.TranslationError):
        i18n.load_locale_file("en", tmp_path)


def test_load_locale_file_rejects_non_string_values(tmp_path: Path):
    (tmp_path / "en.json").write_text(json.dumps({"a.b": 5}), encoding="utf-8")
    with pytest.raises(i18n.TranslationError):
        i18n.load_locale_file("en", tmp_path)


def test_load_translations_loads_every_locale_in_dir(tmp_path: Path):
    (tmp_path / "en.json").write_text(json.dumps({"k": "v-en"}), encoding="utf-8")
    (tmp_path / "de.json").write_text(json.dumps({"k": "v-de"}), encoding="utf-8")
    result = i18n.load_translations(tmp_path)
    assert result == {"en": {"k": "v-en"}, "de": {"k": "v-de"}}


def test_load_translations_missing_dir_returns_empty(tmp_path: Path):
    assert i18n.load_translations(tmp_path / "does-not-exist") == {}


# --- translate(): fallback logic (never crashes, never silently skips) -----


def test_translate_returns_selected_language_value():
    translations = {"de": {"k": "Wert"}, "en": {"k": "value"}}
    assert i18n.translate("k", "de", translations) == "Wert"


def test_translate_falls_back_to_english_when_key_missing_in_selected_language():
    translations = {"de": {}, "en": {"k": "value"}}
    assert i18n.translate("k", "de", translations) == "value"


def test_translate_returns_raw_key_when_missing_everywhere():
    translations = {"de": {}, "en": {}}
    assert i18n.translate("totally.missing.key", "de", translations) == "totally.missing.key"


def test_translate_never_raises_for_unknown_language():
    translations = {"en": {"k": "value"}}
    assert i18n.translate("k", "fr", translations) == "value"
    assert i18n.translate("missing", "fr", translations) == "missing"


def test_translate_formats_placeholders():
    translations = {"en": {"greet": "Hello {name}"}}
    assert i18n.translate("greet", "en", translations, name="World") == "Hello World"


def test_translate_returns_unformatted_string_if_placeholder_missing():
    translations = {"en": {"greet": "Hello {name}"}}
    # No `name` kwarg supplied -> must not raise, falls back to raw text.
    assert i18n.translate("greet", "en", translations) == "Hello {name}"


# --- configure()/t(): the ergonomic module-level API ------------------------


@pytest.fixture(autouse=True)
def _reset_i18n_state():
    """Isolate module-level i18n state across tests."""
    yield
    i18n._state["language"] = i18n.DEFAULT_LANGUAGE
    i18n._state["translations"] = None


def test_configure_and_t_roundtrip(tmp_path: Path):
    (tmp_path / "en.json").write_text(json.dumps({"greeting": "Hello"}), encoding="utf-8")
    (tmp_path / "de.json").write_text(json.dumps({"greeting": "Hallo"}), encoding="utf-8")

    lang = i18n.configure(cli_language="de", directory=tmp_path)
    assert lang == "de"
    assert i18n.t("greeting") == "Hallo"


def test_t_falls_back_to_english_for_missing_key(tmp_path: Path):
    (tmp_path / "en.json").write_text(json.dumps({"only.in.en": "English only"}), encoding="utf-8")
    (tmp_path / "de.json").write_text(json.dumps({}), encoding="utf-8")

    i18n.configure(cli_language="de", directory=tmp_path)
    assert i18n.t("only.in.en") == "English only"


def test_t_never_crashes_on_totally_unknown_key(tmp_path: Path):
    (tmp_path / "en.json").write_text(json.dumps({}), encoding="utf-8")
    i18n.configure(cli_language="en", directory=tmp_path)
    assert i18n.t("nonexistent.key") == "nonexistent.key"


def test_t_lazily_configures_with_real_shipped_locales():
    # No configure() call at all -> t() must still work off the real
    # shipped src/unren/locales/*.json without raising.
    assert i18n.t("menu.title") != ""


# --- real shipped locale files: schema + coverage ---------------------------


def test_shipped_locales_dir_contains_de_and_en():
    directory = i18n.locales_dir()
    assert (directory / "en.json").is_file()
    assert (directory / "de.json").is_file()


def test_shipped_en_and_de_have_identical_key_sets():
    directory = i18n.locales_dir()
    en = i18n.load_locale_file("en", directory)
    de = i18n.load_locale_file("de", directory)
    assert en, "en.json must not be empty"
    assert set(en.keys()) == set(de.keys())


def test_shipped_locales_have_no_empty_values():
    directory = i18n.locales_dir()
    for lang in ("en", "de"):
        table = i18n.load_locale_file(lang, directory)
        for key, value in table.items():
            assert value.strip(), f"{lang}.json key {key!r} has an empty value"
