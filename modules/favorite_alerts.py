"""
modules/favorite_alerts.py — Alerts for user-specified favorite species.

NOTE: The user can mark certain species as "favorites" and get instant
      notifications whenever one visits the feeder, regardless of rarity level.

WHY: Birdfy lets users set favorite species for special notifications. A
     birder might want to know every time a particular bird visits, even
     if it's technically "common" — it could be a personal favorite.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from core.types import BirdSighting

logger = logging.getLogger(__name__)


class FavoriteAlerts:
    """
    Manages favorite species alerts.

    Usage:
        alerts = FavoriteAlerts({"mock_mode": True})
        alerts.add_favorite("American Robin")
        if alerts.is_favorite("American Robin"):
            alerts.send_favorite_alert(sighting)
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.mock_mode = self.config.get("mock_mode", True)
        self._favorites: set[str] = set()
        self._last_alert: dict[str, float] = {}
        self._cooldown_seconds = self.config.get("cooldown_minutes", 60) * 60
        self._sent_count = 0

    def add_favorite(self, species: str) -> None:
        """Add a species to favorites."""
        self._favorites.add(species.lower())
        logger.info("Added favorite: %s", species)

    def remove_favorite(self, species: str) -> bool:
        """Remove a species from favorites."""
        if species.lower() in self._favorites:
            self._favorites.discard(species.lower())
            return True
        return False

    def is_favorite(self, species: str) -> bool:
        """Check if a species is in the favorites list."""
        return species.lower() in self._favorites

    def get_favorites(self) -> list[str]:
        """Get the list of favorite species."""
        return sorted(self._favorites)

    def should_alert(self, sighting: BirdSighting) -> bool:
        """Check if an alert should be sent for this sighting."""
        if not self.is_favorite(sighting.species):
            return False
        if self._is_rate_limited(sighting.species):
            return False
        return True

    def send_favorite_alert(self, sighting: BirdSighting) -> bool:
        """Send a favorite species alert (returns True if sent)."""
        if not self.should_alert(sighting):
            return False
        # NOTE: Actual notification sending is delegated to SMS/WiFi/push modules
        logger.info("Favorite species alert: %s at %s", sighting.species, sighting.timestamp[:19])
        self._last_alert[sighting.species.lower()] = time.time()
        self._sent_count += 1
        return True

    def _is_rate_limited(self, species: str) -> bool:
        """Check rate limiting for a species."""
        key = species.lower()
        last = self._last_alert.get(key)
        if last is None:
            return False
        return (time.time() - last) < self._cooldown_seconds

    def clear_rate_limits(self) -> None:
        """Clear all rate limits."""
        self._last_alert.clear()

    @property
    def sent_count(self) -> int:
        return self._sent_count

    def get_stats(self) -> dict[str, Any]:
        """Return favorite alert statistics."""
        return {
            "favorite_count": len(self._favorites),
            "favorites": self.get_favorites(),
            "alerts_sent": self._sent_count,
        }

    @property
    def favorite_count(self) -> int:
        return len(self._favorites)


__all__ = ["FavoriteAlerts"]
