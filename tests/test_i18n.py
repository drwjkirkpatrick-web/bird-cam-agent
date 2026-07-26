"""tests/test_i18n.py"""

import pytest
from modules.i18n import I18n, TRANSLATIONS

class TestI18n:
    def test_english_default(self):
        i18n = I18n("en")
        assert i18n.t("total_sightings") == "Total Sightings"
    def test_swahili(self):
        i18n = I18n("sw")
        assert i18n.t("total_sightings") == "Idadi ya Maoni"
    def test_spanish(self):
        i18n = I18n("es")
        assert i18n.t("total_sightings") == "Avistamientos Totales"
    def test_french(self):
        i18n = I18n("fr")
        assert i18n.t("total_sightings") == "Observations Totales"
    def test_fallback_to_english(self):
        i18n = I18n("xx")  # Nonexistent language
        assert i18n.t("total_sightings") == "Total Sightings"
    def test_missing_key_returns_key(self):
        i18n = I18n("en")
        assert i18n.t("nonexistent_key") == "nonexistent_key"
    def test_set_language(self):
        i18n = I18n("en")
        assert i18n.set_language("sw") is True
        assert i18n.current_language == "sw"
    def test_set_invalid_language(self):
        i18n = I18n("en")
        assert i18n.set_language("xx") is False
    def test_available_languages(self):
        i18n = I18n("en")
        langs = i18n.get_available_languages()
        assert "en" in langs
        assert "sw" in langs
    def test_add_language(self):
        i18n = I18n("en")
        i18n.add_language("de", {"total_sightings": "Gesamtsichtungen"})
        assert i18n.set_language("de") is True
        assert i18n.t("total_sightings") == "Gesamtsichtungen"
