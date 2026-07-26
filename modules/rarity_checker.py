"""
modules/rarity_checker.py — Check if an identified bird is rare.

NOTE: This module loads a USER-SUPPLIED rarity YAML file and checks
      whether a species is rare for the user's location. It does NOT
      contain any hardcoded bird data — the user provides their own
      rarity list based on their region.

WHY: Bird rarity is highly location-dependent. A bird that's common in
     Oregon might be rare in Florida, and vice versa. Rather than shipping
     a static database, we provide the TOOL and let the user supply the
     DATA that matches their region.

Rarity file format (user creates this):
    ```yaml
    location: "Pacific Northwest, USA"
    species:
      - name: "American Robin"
        scientific_name: "Turdus migratorius"
        rarity: "common"
        notes: "Year-round resident"
      - name: "Snowy Owl"
        scientific_name: "Bubo scandiacus"
        rarity: "rare"
        notes: "Irruptive winter visitor"
    ```
"""

from __future__ import annotations

import difflib
import logging
import os
from typing import Any

from core.config import RarityConfig
from core.types import RarityLevel

logger = logging.getLogger(__name__)


class RarityChecker:
    """
    Check bird species rarity based on a user-supplied rarity file.

    Usage:
        checker = RarityChecker(config.rarity)
        level = checker.check_rarity("Snowy Owl")
        if checker.is_rare("Snowy Owl"):
            print("Rare bird detected!")
    """

    def __init__(self, config: RarityConfig):
        self.config = config
        self._rarity_data: dict[str, dict[str, Any]] = {}
        self._location_name = config.location_name
        self._load_rarity_data()

    def _load_rarity_data(self) -> None:
        """Load the rarity YAML file if it exists."""
        path = self.config.rarity_file
        if not path or not os.path.exists(path):
            logger.info(
                "No rarity file found at '%s' — all birds default to COMMON",
                path or "(not set)",
            )
            return

        try:
            self._rarity_data = self.load_rarity_data(path)
            logger.info(
                "Loaded %d species from rarity file for location: %s",
                len(self._rarity_data),
                self._location_name or "unknown",
            )
        except Exception as e:
            logger.error("Failed to load rarity file: %s", e)
            self._rarity_data = {}

    def load_rarity_data(self, path: str) -> dict[str, dict[str, Any]]:
        """
        Load a rarity YAML file and return a species → data mapping.

        NOTE: Returns a dict keyed by lowercase species name for
              case-insensitive lookups.
        """
        import yaml

        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}

        if not self._location_name and "location" in data:
            self._location_name = data.get("location", "")

        species_list = data.get("species", [])
        if not isinstance(species_list, list):
            logger.warning("Rarity file 'species' key is not a list — ignoring")
            return {}

        result: dict[str, dict[str, Any]] = {}
        for entry in species_list:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name", "")
            if not name:
                continue
            key = name.lower().strip()
            result[key] = {
                "name": name,
                "scientific_name": entry.get("scientific_name", ""),
                "rarity": entry.get("rarity", "common"),
                "notes": entry.get("notes", ""),
                "best_season": entry.get("best_season", ""),
            }

        return result

    def check_rarity(
        self, species: str, scientific_name: str = ""
    ) -> RarityLevel:
        """
        Check the rarity level of a species.

        Returns a RarityLevel. Unknown species default to COMMON
        (or the configured default_rarity).
        """
        if not species or species == "Unknown":
            return RarityLevel.COMMON

        info = self.get_rarity_info(species)
        if info is None:
            # Try fuzzy match
            fuzzy = self._fuzzy_match(species)
            if fuzzy:
                info = self._rarity_data.get(fuzzy)

        if info is None:
            default = self.config.default_rarity
            return RarityLevel.from_string(default)

        return RarityLevel.from_string(info.get("rarity", "common"))

    def is_rare(
        self, species: str, threshold: RarityLevel = RarityLevel.RARE
    ) -> bool:
        """
        Check if a species is at or above the rarity threshold.

        Default threshold is RARE — returns True for RARE, VERY_RARE, ACCIDENTAL.
        """
        level = self.check_rarity(species)
        return level >= threshold

    def get_rarity_info(self, species: str) -> dict[str, Any] | None:
        """
        Get full rarity info for a species.

        Returns None if the species is not in the rarity database.
        """
        if not species:
            return None
        key = species.lower().strip()
        return self._rarity_data.get(key)

    def add_species(
        self,
        species: str,
        rarity_level: str | RarityLevel,
        notes: str = "",
        scientific_name: str = "",
    ) -> None:
        """Add or update a species in the in-memory rarity database."""
        if isinstance(rarity_level, RarityLevel):
            rarity_str = rarity_level.value
        else:
            rarity_str = rarity_level

        key = species.lower().strip()
        self._rarity_data[key] = {
            "name": species,
            "scientific_name": scientific_name,
            "rarity": rarity_str,
            "notes": notes,
            "best_season": "",
        }
        logger.info("Added species '%s' with rarity '%s'", species, rarity_str)

    def list_all(self) -> dict[str, dict[str, Any]]:
        """Return the full rarity database."""
        return dict(self._rarity_data)

    def _fuzzy_match(self, species: str) -> str | None:
        """
        Find a close match for a species name using fuzzy matching.

        NOTE: This handles cases like "American Robin" vs "american  robin"
              or slight typos. Uses difflib for a similarity ratio.
        """
        if not species or not self._rarity_data:
            return None

        query = species.lower().strip()
        best_match = None
        best_ratio = 0.0
        threshold = 0.8  # 80% similarity required

        for key in self._rarity_data:
            ratio = difflib.SequenceMatcher(None, query, key).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = key

        if best_ratio >= threshold and best_match:
            logger.debug(
                "Fuzzy match: '%s' -> '%s' (%.0f%% match)",
                species,
                self._rarity_data[best_match]["name"],
                best_ratio * 100,
            )
            return best_match

        return None

    @property
    def species_count(self) -> int:
        """Number of species in the rarity database."""
        return len(self._rarity_data)

    @property
    def location_name(self) -> str:
        """The location name from the rarity file."""
        return self._location_name or ""