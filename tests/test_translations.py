"""Integrity tests for translations.py.

The translation tables are hand-maintained across many languages and
merged from multiple topic dicts. These tests catch the classic rot:
keys present in English but missing in a locale, and printf/format
placeholders that differ between translations of the same key (which
crashes at render time).
"""

import re

import pytest

from conftest import load_module


@pytest.fixture(scope="module")
def translations():
    return load_module("translations")


PLACEHOLDER_RE = re.compile(r"{[^{}]*}|\%\(?[a-zA-Z_]+\)?[sd]|%[sd]")


def _placeholder_set(text):
    return sorted(PLACEHOLDER_RE.findall(text))


def test_english_is_the_reference_language(translations):
    assert "en" in translations.TRANSLATIONS
    # English must be non-trivially populated.
    assert len(translations.TRANSLATIONS["en"]) > 100


def test_every_locale_key_exists_in_english(translations):
    en = translations.TRANSLATIONS["en"]
    orphans = {}
    for lang, entries in translations.TRANSLATIONS.items():
        if lang == "en":
            continue
        missing_in_en = sorted(set(entries) - set(en))
        if missing_in_en:
            orphans[lang] = missing_in_en
    assert not orphans, f"Keys missing from 'en': {orphans}"


def test_format_placeholders_match_english(translations):
    """Same key in any language must use the same placeholders as 'en'."""
    en = translations.TRANSLATIONS["en"]
    mismatches = []
    for lang, entries in translations.TRANSLATIONS.items():
        if lang == "en":
            continue
        for key, value in entries.items():
            if not isinstance(value, str):
                continue
            reference = en.get(key)
            if not isinstance(reference, str):
                continue
            if _placeholder_set(value) != _placeholder_set(reference):
                mismatches.append((lang, key))
    assert not mismatches, f"Placeholder drift: {mismatches}"


def test_tr_falls_back_to_english_then_key(translations, monkeypatch):
    tr = translations.tr
    en_key = next(iter(translations.TRANSLATIONS["en"]))

    class FakePm:
        class profile(dict):
            pass

    pm = FakePm()
    pm.profile = {}

    monkeypatch.setattr(translations, "mw", type("M", (), {"pm": pm})())

    # Known key in English.
    assert tr(en_key) == translations.TRANSLATIONS["en"][en_key]

    # Unknown key -> provided default, then the key itself.
    assert tr("totally_bogus_key", "fallback") == "fallback"
    assert tr("totally_bogus_key") == "totally_bogus_key"


def test_unknown_language_falls_back_to_english(translations, monkeypatch):
    pm = type("P", (), {})()
    pm.profile = {"onigiri_language": "xx-XX"}
    monkeypatch.setattr(translations, "mw", type("M", (), {"pm": pm})())
    en_key = next(iter(translations.TRANSLATIONS["en"]))
    assert translations.tr(en_key) == translations.TRANSLATIONS["en"][en_key]
    assert translations.current_language() == "en"
