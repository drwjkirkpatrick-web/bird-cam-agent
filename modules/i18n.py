"""
modules/i18n.py — Multi-language dashboard and alert translations.

NOTE: Provides internationalization for dashboard text and alert messages.
      Supports English, Swahili, Spanish, and French out of the box, with
      easy addition of new languages.

WHY: Birdfy's app is multi-language. A bird cam deployed in Kenya should
     be able to send alerts in Swahili; one in Oregon could use Spanish.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# NOTE: Translation strings for supported languages
TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "total_sightings": "Total Sightings",
        "unique_species": "Unique Species",
        "rarest_bird": "Rarest Bird",
        "last_sighting": "Last Sighting",
        "recent_sightings": "Recent Sightings",
        "no_sightings": "No sightings yet. Start the camera to begin monitoring.",
        "bird_alert": "BIRD ALERT",
        "was_spotted_at": "was spotted at",
        "rare_bird": "Rare Bird",
        "test_notification": "Test SMS sent successfully!",
        "back_to_dashboard": "Back to Dashboard",
        "all_sightings": "All Sightings",
        "species": "Species",
        "rarity": "Rarity",
        "confidence": "Confidence",
        "date": "Date",
        "location": "Location",
        "notes": "Notes",
        "scientific_name": "Scientific Name",
        "alternative_species": "Alternative Species",
        "page": "Page",
        "of": "of",
        "prev": "Prev",
        "next": "Next",
        "feeder_empty": "Feeder is empty! Please refill.",
        "low_battery": "Low battery warning",
        "system_healthy": "System Healthy",
        "system_warning": "System Warning",
        "system_critical": "System Critical",
    },
    "sw": {
        "total_sightings": "Idadi ya Maoni",
        "unique_species": "Aina Tofauti",
        "rarest_bird": "Ndege Mwadimu Zaidi",
        "last_sighting": "Muoni wa Mwisho",
        "recent_sightings": "Maoni ya Karibuni",
        "no_sightings": "Hakuna maoni bado. Anza kamera kuanza ufuatiliaji.",
        "bird_alert": "TAHADHARI YA NDEGE",
        "was_spotted_at": "imeonekana saa",
        "rare_bird": "Ndege Mwadimu",
        "test_notification": "Ujumbe wa majaribio umetumwa!",
        "back_to_dashboard": "Rudi kwenye Dashibodi",
        "all_sightings": "Maoni Yote",
        "species": "Aina",
        "rarity": "Uadimu",
        "confidence": "Uhakika",
        "date": "Tarehe",
        "location": "Eneo",
        "notes": "Maelezo",
        "scientific_name": "Jina la Sayansi",
        "alternative_species": "Aina Nyingine zinazowezekana",
        "page": "Ukurasa",
        "of": "kati ya",
        "prev": "Tangulia",
        "next": "Inayofuata",
        "feeder_empty": "Chakula kimeisha! Tafadhali jaza tena.",
        "low_battery": "Onyo la betri ya chini",
        "system_healthy": "Mfumo ni Salama",
        "system_warning": "Onyo la Mfumo",
        "system_critical": "Hali ya Hatari ya Mfumo",
    },
    "es": {
        "total_sightings": "Avistamientos Totales",
        "unique_species": "Especies Unicas",
        "rarest_bird": "Ave Mas Rara",
        "last_sighting": "Ultimo Avistamiento",
        "recent_sightings": "Avistamientos Recientes",
        "no_sightings": "Sin avistamientos aun. Inicie la camara para comenzar.",
        "bird_alert": "ALERTA DE AVE",
        "was_spotted_at": "fue vista a las",
        "rare_bird": "Ave Rara",
        "test_notification": "Notificacion de prueba enviada!",
        "back_to_dashboard": "Volver al Panel",
        "all_sightings": "Todos los Avistamientos",
        "species": "Especie",
        "rarity": "Rareza",
        "confidence": "Confianza",
        "date": "Fecha",
        "location": "Ubicacion",
        "notes": "Notas",
        "scientific_name": "Nombre Cientifico",
        "alternative_species": "Especies Alternativas",
        "page": "Pagina",
        "of": "de",
        "prev": "Anterior",
        "next": "Siguiente",
        "feeder_empty": "El comedero esta vacio! Por favor rellenar.",
        "low_battery": "Advertencia de bateria baja",
        "system_healthy": "Sistema Saludable",
        "system_warning": "Advertencia del Sistema",
        "system_critical": "Sistema Critico",
    },
    "fr": {
        "total_sightings": "Observations Totales",
        "unique_species": "Especes Uniques",
        "rarest_bird": "Oiseau le Plus Rare",
        "last_sighting": "Derniere Observation",
        "recent_sightings": "Observations Recententes",
        "no_sightings": "Aucune observation. Demarrez la camera pour commencer.",
        "bird_alert": "ALERTE OISEAU",
        "was_spotted_at": "a ete observe a",
        "rare_bird": "Oiseau Rare",
        "test_notification": "Notification de test envoyee!",
        "back_to_dashboard": "Retour au Tableau de Bord",
        "all_sightings": "Toutes les Observations",
        "species": "Espece",
        "rarity": "Rarete",
        "confidence": "Confiance",
        "date": "Date",
        "location": "Emplacement",
        "notes": "Notes",
        "scientific_name": "Nom Scientifique",
        "alternative_species": "Especes Alternatives",
        "page": "Page",
        "of": "sur",
        "prev": "Precedent",
        "next": "Suivant",
        "feeder_empty": "Le mangeoire est vide! Veuillez remplir.",
        "low_battery": "Avertissement de batterie faible",
        "system_healthy": "Systeme Sain",
        "system_warning": "Avertissement Systeme",
        "system_critical": "Systeme Critique",
    },
}


class I18n:
    """
    Internationalization helper for dashboard and alerts.

    Usage:
        i18n = I18n("sw")  # Swahili
        text = i18n.t("total_sightings")  # "Idadi ya Maoni"
    """

    SUPPORTED_LANGUAGES = list(TRANSLATIONS.keys())

    def __init__(self, language: str = "en"):
        self.language = language if language in TRANSLATIONS else "en"
        self._fallback = "en"

    def t(self, key: str, **kwargs) -> str:
        """
        Translate a key to the current language.

        Supports format string substitution via kwargs.
        """
        translations = TRANSLATIONS.get(self.language, {})
        text = translations.get(key, TRANSLATIONS[self._fallback].get(key, key))

        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError):
                return text
        return text

    def set_language(self, language: str) -> bool:
        """Change the current language."""
        if language in TRANSLATIONS:
            self.language = language
            return True
        return False

    def get_available_languages(self) -> list[str]:
        """Get list of supported language codes."""
        return self.SUPPORTED_LANGUAGES

    def add_language(self, code: str, translations: dict[str, str]) -> None:
        """Add a new language translation set."""
        TRANSLATIONS[code] = translations
        if code not in self.SUPPORTED_LANGUAGES:
            self.SUPPORTED_LANGUAGES.append(code)

    @property
    def current_language(self) -> str:
        return self.language


__all__ = ["I18n", "TRANSLATIONS"]
