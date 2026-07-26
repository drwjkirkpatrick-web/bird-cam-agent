"""
modules/bird_book.py — Virtual bird species collection.

NOTE: A digital "bird book" showing all species seen at the feeder, with
      first sighting date, total count, best photo, and rarity. Like a
      life list but with photos and stats.

WHY: Birdfy and Bird Buddy both feature a "bird book" in their app — a
     collection of all species the user has seen. This is a core engagement
     feature that turns raw sightings into a personal collection.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from core.types import BirdSighting, RarityLevel

logger = logging.getLogger(__name__)


@dataclass
class BookEntry:
    """A single species entry in the bird book."""
    species: str
    scientific_name: str = ""
    first_seen: str = ""
    last_seen: str = ""
    total_sightings: int = 0
    rarity: str = "common"
    best_photo_path: str = ""
    notes: str = ""
    habitat: str = ""


class BirdBook:
    """
    A digital collection of all species seen at the feeder.

    Usage:
        book = BirdBook()
        book.add_sighting(sighting)
        entries = book.get_collection()
        entry = book.get_entry("American Robin")
    """

    def __init__(self):
        self._entries: dict[str, BookEntry] = {}

    def add_sighting(self, sighting: BirdSighting) -> None:
        """Add a sighting to the bird book."""
        species = sighting.species
        if species not in self._entries:
            self._entries[species] = BookEntry(
                species=species,
                scientific_name=sighting.scientific_name,
                first_seen=sighting.timestamp,
                last_seen=sighting.timestamp,
                total_sightings=1,
                rarity=sighting.rarity_level.value,
                best_photo_path=sighting.photo_path,
                notes=sighting.notes,
            )
            logger.info("New bird book entry: %s", species)
        else:
            entry = self._entries[species]
            entry.last_seen = sighting.timestamp
            entry.total_sightings += 1
            # NOTE: Keep the best photo (first one with highest confidence)
            if sighting.photo_path and not entry.best_photo_path:
                entry.best_photo_path = sighting.photo_path

    def get_collection(self) -> list[dict[str, Any]]:
        """Return all entries in the bird book, sorted by first sighting date."""
        entries = sorted(self._entries.values(), key=lambda e: e.first_seen, reverse=True)
        return [
            {
                "species": e.species,
                "scientific_name": e.scientific_name,
                "first_seen": e.first_seen,
                "last_seen": e.last_seen,
                "total_sightings": e.total_sightings,
                "rarity": e.rarity,
                "best_photo": e.best_photo_path,
                "notes": e.notes,
            }
            for e in entries
        ]

    def get_entry(self, species: str) -> dict[str, Any] | None:
        """Get a specific species entry."""
        entry = self._entries.get(species)
        if not entry:
            return None
        return {
            "species": entry.species,
            "scientific_name": entry.scientific_name,
            "first_seen": entry.first_seen,
            "last_seen": entry.last_seen,
            "total_sightings": entry.total_sightings,
            "rarity": entry.rarity,
            "best_photo": entry.best_photo_path,
            "notes": entry.notes,
        }

    def get_collection_stats(self) -> dict[str, Any]:
        """Return summary statistics about the collection."""
        rarity_counts: dict[str, int] = {}
        for entry in self._entries.values():
            r = entry.rarity
            rarity_counts[r] = rarity_counts.get(r, 0) + 1

        return {
            "total_species": len(self._entries),
            "total_sightings": sum(e.total_sightings for e in self._entries.values()),
            "rarity_breakdown": rarity_counts,
            "most_sighted": max(self._entries.values(), key=lambda e: e.total_sightings).species if self._entries else None,
            "rarest_species": min(self._entries.values(), key=lambda e: list(RarityLevel).index(RarityLevel.from_string(e.rarity))).species if self._entries else None,
        }

    def get_recent_additions(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recently added species (new lifers)."""
        entries = sorted(self._entries.values(), key=lambda e: e.first_seen, reverse=True)
        return [
            {"species": e.species, "first_seen": e.first_seen, "rarity": e.rarity}
            for e in entries[:limit]
        ]

    @property
    def species_count(self) -> int:
        """Number of unique species in the collection."""
        return len(self._entries)

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()


__all__ = ["BirdBook", "BookEntry"]
