"""
modules/migration_tracker.py — Bird migration pattern tracking.

NOTE: Tracks seasonal bird movements by monitoring when species appear and
      disappear from the feeder area. Can detect migration timing, compare
      year-over-year patterns, and predict arrival dates.

WHY: Migration timing is one of the most interesting aspects of birdwatching.
     This module helps answer "when do the Rufous Hummingbirds arrive?" or
     "when did the Juncos leave last winter?"
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.types import BirdSighting

logger = logging.getLogger(__name__)


@dataclass
class MigrationRecord:
    """A single species migration record."""
    species: str
    first_seen: str
    last_seen: str
    sighting_count: int = 0
    is_present: bool = True


class MigrationTracker:
    """
    Tracks bird migration patterns from sighting data.

    Usage:
        tracker = MigrationTracker()
        tracker.add_sighting(sighting)
        status = tracker.get_migration_status("Rufous Hummingbird")
        arrivals = tracker.get_spring_arrivals(year=2026)
    """

    def __init__(self):
        self._records: dict[str, MigrationRecord] = {}
        self._sighting_dates: dict[str, list[str]] = defaultdict(list)

    def add_sighting(self, sighting: BirdSighting) -> None:
        """Record a sighting for migration tracking."""
        species = sighting.species
        ts = sighting.timestamp

        if species not in self._records:
            self._records[species] = MigrationRecord(
                species=species,
                first_seen=ts,
                last_seen=ts,
                sighting_count=1,
                is_present=True,
            )
        else:
            record = self._records[species]
            record.last_seen = ts
            record.sighting_count += 1
            record.is_present = True

        self._sighting_dates[species].append(ts)

    def mark_absent(self, species: str, date: str) -> None:
        """Mark a species as absent (departed) on a given date."""
        if species in self._records:
            self._records[species].is_present = False

    def get_migration_status(self, species: str) -> dict[str, Any]:
        """Get migration status for a species."""
        record = self._records.get(species)
        if not record:
            return {
                "species": species,
                "status": "never_seen",
                "first_seen": None,
                "last_seen": None,
                "is_present": False,
            }

        return {
            "species": species,
            "status": "present" if record.is_present else "departed",
            "first_seen": record.first_seen,
            "last_seen": record.last_seen,
            "sighting_count": record.sighting_count,
            "is_present": record.is_present,
        }

    def get_spring_arrivals(self, year: int | None = None) -> list[dict[str, Any]]:
        """Get species that first appeared in spring (Mar-May) of the given year."""
        arrivals = []
        for species, record in self._records.items():
            try:
                dt = datetime.fromisoformat(record.first_seen.replace("Z", "+00:00"))
                if dt.month in (3, 4, 5):
                    if year is None or dt.year == year:
                        arrivals.append({
                            "species": species,
                            "first_seen": record.first_seen,
                            "month": dt.month,
                            "day": dt.day,
                        })
            except (ValueError, AttributeError):
                pass
        arrivals.sort(key=lambda x: x["first_seen"])
        return arrivals

    def get_autumn_departures(self, year: int | None = None) -> list[dict[str, Any]]:
        """Get species last seen in autumn (Sep-Nov) — likely migrants departing."""
        departures = []
        for species, record in self._records.items():
            try:
                dt = datetime.fromisoformat(record.last_seen.replace("Z", "+00:00"))
                if dt.month in (9, 10, 11):
                    if year is None or dt.year == year:
                        departures.append({
                            "species": species,
                            "last_seen": record.last_seen,
                            "month": dt.month,
                            "day": dt.day,
                        })
            except (ValueError, AttributeError):
                pass
        departures.sort(key=lambda x: x["last_seen"])
        return departures

    def get_present_species(self) -> list[str]:
        """Return list of species currently marked as present."""
        return [s for s, r in self._records.items() if r.is_present]

    def get_absent_species(self) -> list[str]:
        """Return list of species marked as departed."""
        return [s for s, r in self._records.items() if not r.is_present]

    def get_all_records(self) -> dict[str, dict[str, Any]]:
        """Return all migration records."""
        return {
            species: {
                "first_seen": r.first_seen,
                "last_seen": r.last_seen,
                "sighting_count": r.sighting_count,
                "is_present": r.is_present,
            }
            for species, r in self._records.items()
        }

    def predict_arrival(self, species: str) -> dict[str, Any]:
        """
        Predict arrival window based on historical first-seen dates.

        NOTE: Needs at least 2 years of data for a meaningful prediction.
        """
        dates = self._sighting_dates.get(species, [])
        first_seen_dates = []
        for d in dates:
            try:
                dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
                first_seen_dates.append(dt)
            except (ValueError, AttributeError):
                pass

        if len(first_seen_dates) < 2:
            return {
                "species": species,
                "prediction": "insufficient_data",
                "years_of_data": len(first_seen_dates),
            }

        # Group by year and find first sighting per year
        by_year: dict[int, datetime] = {}
        for dt in first_seen_dates:
            if dt.year not in by_year or dt < by_year[dt.year]:
                by_year[dt.year] = dt

        years = sorted(by_year.keys())
        if len(years) < 2:
            return {
                "species": species,
                "prediction": "insufficient_data",
                "years_of_data": len(years),
            }

        # Average day-of-year of first sightings
        day_of_years = [by_year[y].timetuple().tm_yday for y in years]
        avg_doy = sum(day_of_years) / len(day_of_years)
        min_doy = min(day_of_years)
        max_doy = max(day_of_years)

        return {
            "species": species,
            "prediction": "estimated",
            "avg_arrival_doy": round(avg_doy),
            "earliest_doy": min_doy,
            "latest_doy": max_doy,
            "years_of_data": len(years),
            "arrival_window": f"Day {min_doy} to Day {max_doy}",
        }

    @property
    def tracked_species_count(self) -> int:
        return len(self._records)

    def clear(self) -> None:
        self._records.clear()
        self._sighting_dates.clear()


__all__ = ["MigrationTracker", "MigrationRecord"]