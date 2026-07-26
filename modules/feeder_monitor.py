"""
modules/feeder_monitor.py — Feeder activity monitoring and analytics.

NOTE: Tracks bird feeder visitation patterns — frequency, duration, species
      mix, time-of-day patterns, and feeder utilization metrics.

WHY: Understanding feeder activity helps optimize placement, food types, and
     capture timing. A feeder that gets 50 visits/day vs 2 visits/day needs
     different monitoring strategies.
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
class FeederVisit:
    """A single feeder visit by a bird."""
    sighting_id: str
    species: str
    timestamp: str
    duration_seconds: float = 0.0
    photo_path: str = ""


class FeederMonitor:
    """
    Tracks and analyzes feeder visitation patterns.

    Usage:
        monitor = FeederMonitor()
        monitor.record_visit(sighting)
        stats = monitor.get_activity_stats()
    """

    def __init__(self):
        self._visits: list[FeederVisit] = []
        self._max_visits = 1000

    def record_visit(self, sighting: BirdSighting, duration: float = 0.0) -> None:
        """Record a feeder visit from a sighting."""
        visit = FeederVisit(
            sighting_id=sighting.sighting_id,
            species=sighting.species,
            timestamp=sighting.timestamp,
            duration_seconds=duration,
            photo_path=sighting.photo_path,
        )
        self._visits.append(visit)
        if len(self._visits) > self._max_visits:
            self._visits = self._visits[-self._max_visits:]
        logger.debug("Recorded feeder visit: %s at %s", sighting.species, sighting.timestamp)

    def get_activity_stats(self) -> dict[str, Any]:
        """Return comprehensive feeder activity statistics."""
        if not self._visits:
            return {
                "total_visits": 0,
                "unique_species": 0,
                "visits_by_hour": {},
                "visits_by_species": {},
                "avg_visits_per_day": 0.0,
                "peak_hour": None,
                "most_visited_species": None,
            }

        visits_by_hour: dict[int, int] = defaultdict(int)
        visits_by_species: dict[str, int] = defaultdict(int)
        visits_by_date: dict[str, int] = defaultdict(int)

        for visit in self._visits:
            try:
                dt = datetime.fromisoformat(visit.timestamp.replace("Z", "+00:00"))
                visits_by_hour[dt.hour] += 1
                visits_by_date[dt.strftime("%Y-%m-%d")] += 1
            except (ValueError, AttributeError):
                pass
            visits_by_species[visit.species] += 1

        peak_hour = max(visits_by_hour, key=lambda k: visits_by_hour[k]) if visits_by_hour else None
        most_visited = max(visits_by_species, key=lambda k: visits_by_species[k]) if visits_by_species else None
        avg_per_day = len(self._visits) / max(len(visits_by_date), 1)

        return {
            "total_visits": len(self._visits),
            "unique_species": len(visits_by_species),
            "visits_by_hour": dict(visits_by_hour),
            "visits_by_species": dict(visits_by_species),
            "visits_by_date": dict(visits_by_date),
            "avg_visits_per_day": round(avg_per_day, 1),
            "peak_hour": peak_hour,
            "most_visited_species": most_visited,
        }

    def get_species_frequency(self) -> dict[str, float]:
        """Return visit frequency percentage per species."""
        if not self._visits:
            return {}
        total = len(self._visits)
        counts: dict[str, int] = defaultdict(int)
        for v in self._visits:
            counts[v.species] += 1
        return {species: round(count / total * 100, 1) for species, count in counts.items()}

    def get_hourly_pattern(self) -> dict[int, int]:
        """Return visit counts by hour of day (0-23)."""
        result: dict[int, int] = defaultdict(int)
        for visit in self._visits:
            try:
                dt = datetime.fromisoformat(visit.timestamp.replace("Z", "+00:00"))
                result[dt.hour] += 1
            except (ValueError, AttributeError):
                pass
        return dict(result)

    def get_recent_visits(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent visits as dicts, most recent first."""
        recent = self._visits[-limit:]
        return [
            {
                "sighting_id": v.sighting_id,
                "species": v.species,
                "timestamp": v.timestamp,
                "duration_seconds": v.duration_seconds,
            }
            for v in reversed(recent)
        ]

    def clear(self) -> None:
        """Clear all visit history."""
        self._visits.clear()

    @property
    def total_visits(self) -> int:
        return len(self._visits)


__all__ = ["FeederMonitor", "FeederVisit"]