"""tests/test_favorite_alerts.py"""

from datetime import datetime, timezone

import pytest
from core.types import BirdSighting, RarityLevel
from modules.favorite_alerts import FavoriteAlerts

@pytest.fixture
def alerts():
    return FavoriteAlerts({"mock_mode": True})

@pytest.fixture
def sighting():
    return BirdSighting(
        species="American Robin",
        confidence=0.9,
        rarity_level=RarityLevel.COMMON,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

class TestFavorites:
    def test_add_favorite(self, alerts):
        alerts.add_favorite("American Robin")
        assert alerts.is_favorite("American Robin") is True
    def test_remove_favorite(self, alerts):
        alerts.add_favorite("American Robin")
        assert alerts.remove_favorite("American Robin") is True
        assert alerts.is_favorite("American Robin") is False
    def test_not_favorite(self, alerts):
        assert alerts.is_favorite("Crow") is False
    def test_should_alert(self, alerts, sighting):
        alerts.add_favorite("American Robin")
        assert alerts.should_alert(sighting) is True
    def test_should_not_alert_non_favorite(self, alerts, sighting):
        assert alerts.should_alert(sighting) is False
    def test_send_alert(self, alerts, sighting):
        alerts.add_favorite("American Robin")
        assert alerts.send_favorite_alert(sighting) is True
        assert alerts.sent_count == 1
    def test_rate_limited(self, alerts, sighting):
        alerts.add_favorite("American Robin")
        alerts.send_favorite_alert(sighting)
        assert alerts.send_favorite_alert(sighting) is False
    def test_get_favorites(self, alerts):
        alerts.add_favorite("Robin")
        alerts.add_favorite("Crow")
        favs = alerts.get_favorites()
        assert len(favs) == 2
    def test_stats(self, alerts):
        alerts.add_favorite("Robin")
        stats = alerts.get_stats()
        assert stats["favorite_count"] == 1
