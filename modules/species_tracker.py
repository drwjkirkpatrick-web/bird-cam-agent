"""
modules/species_tracker.py — Species tracking and diversity metrics.

NOTE: Tracks which species have been seen, when, and how often. Provides
      diversity metrics (Shannon index, species richness, accumulation curves)
      and can generate "life list" reports for the bird cam location.

WHY: A core joy of birdwatching is tracking your species list. This module
     turns raw sightings into meaningful diversity metrics and life lists.
"""

from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from core.types import BirdSighting, RarityLevel

logger = logging.getLogger(__name__)


class SpeciesTracker:
    """
    Tracks species observations and computes diversity metrics.

    Usage:
        tracker = SpeciesTracker()
        tracker.add_sighting(sighting)
        life_list = tracker.get_life_list()
        diversity = tracker.get_diversity_metrics()
    """

    def __init__(self):
        self._sightings: list[BirdSighting] = []
        self._species_first_seen: dict[str, str] = {}  # species → timestamp
        self._species_counts: Counter = Counter()
        self._max_sightings = 5000

    def add_sighting(self, sighting: BirdSighting) -> None:
        """Add a sighting to the tracker."""
        self._sightings.append(sighting)
        species = sighting.species

        if species not in self._species_first_seen:
            self._species_first_seen[species] = sighting.timestamp
            logger.info("New species added to life list: %s", species)

        self._species_counts[species] += 1

        if len(self._sightings) > self._max_sightings:
            self._sightings = self._sightings[-self._max_sightings:]

    def get_life_list(self) -> list[dict[str, Any]]:
        """
        Return the life list — all species seen, with first sighting date
        and total count. Sorted by first sighting date (most recent first).
        """
        life_list = []
        for species, first_seen in self._species_first_seen.items():
            life_list.append({
                "species": species,
                "first_seen": first_seen,
                "total_sightings": self._species_counts[species],
            })
        life_list.sort(key=lambda x: x["first_seen"], reverse=True)
        return life_list

    def get_diversity_metrics(self) -> dict[str, Any]:
        """
        Compute biodiversity metrics.

        - species_richness: total unique species
        - shannon_index: Shannon diversity index (H)
        - simpson_index: Simpson diversity index (1-D)
        - evenness: Pielou's evenness (J = H / ln(S))
        - total_observations: total sighting count
        """
        total = sum(self._species_counts.values())
        if total == 0:
            return {
                "species_richness": 0,
                "shannon_index": 0.0,
                "simpson_index": 0.0,
                "evenness": 0.0,
                "total_observations": 0,
            }

        richness = len(self._species_counts)
        proportions = [count / total for count in self._species_counts.values()]

        # Shannon index: H = -sum(p_i * ln(p_i))
        shannon = -sum(p * math.log(p) for p in proportions if p > 0)

        # Simpson index: 1 - sum(p_i^2)
        simpson = 1 - sum(p ** 2 for p in proportions)

        # Pielou's evenness: J = H / ln(S)
        evenness = shannon / math.log(richness) if richness > 1 else 0.0

        return {
            "species_richness": richness,
            "shannon_index": round(shannon, 3),
            "simpson_index": round(simpson, 3),
            "evenness": round(evenness, 3),
            "total_observations": total,
        }

    def get_species_counts(self) -> dict[str, int]:
        """Return sighting counts per species."""
        return dict(self._species_counts)

    def get_rarest_species_seen(self) -> str | None:
        """Return the rarest species that has been observed."""
        if not self._sightings:
            return None
        rarest = None
        rarest_level = RarityLevel.COMMON
        for s in self._sightings:
            if s.rarity_level > rarest_level:
                rarest_level = s.rarity_level
                rarest = s.species
        return rarest

    def get_new_species_this_session(self, session_start: str) -> list[str]:
        """Return species first seen after the given session start timestamp."""
        return [
            species for species, first_seen in self._species_first_seen.items()
            if first_seen >= session_start
        ]

    def get_species_summary(self, species: str) -> dict[str, Any]:
        """Get a summary for a specific species."""
        count = self._species_counts.get(species, 0)
        first_seen = self._species_first_seen.get(species, "")
        return {
            "species": species,
            "total_sightings": count,
            "first_seen": first_seen,
        }

    def check_lifer(self, sighting: BirdSighting) -> bool:
        """Check if this sighting is a new life-list species."""
        return sighting.species not in self._species_first_seen

    @property
    def species_count(self) -> int:
        """Number of unique species seen."""
        return len(self._species_counts)

    @property
    def total_sightings(self) -> int:
        """Total number of sightings tracked."""
        return len(self._sightings)

    def clear(self) -> None:
        """Clear all tracking data."""
        self._sightings.clear()
        self._species_first_seen.clear()
        self._species_counts.clear()


__all__ = ["SpeciesTracker"]