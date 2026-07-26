"""tests/test_push_notifier.py"""

import time
from datetime import datetime, timezone

import pytest
from core.types import BirdSighting, RarityLevel
from modules.push_notifier import PushNotifier

@pytest.fixture
def notifier():
    return PushNotifier({"mock_mode": True, "cooldown_minutes": 30})

@pytest.fixture
def rare_sighting():
    return BirdSighting(
        species="Snowy Owl",
        confidence=0.95,
        rarity_level=RarityLevel.RARE,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

class TestPush:
    def test_send_alert(self, notifier, rare_sighting):
        assert notifier.send_rare_bird_alert(rare_sighting) is True
        assert notifier.sent_count == 1
    def test_rate_limited(self, notifier, rare_sighting):
        notifier.send_rare_bird_alert(rare_sighting)
        assert notifier.send_rare_bird_alert(rare_sighting) is False
    def test_test_notification(self, notifier):
        assert notifier.test_notification() is True
    def test_send_notification(self, notifier):
        assert notifier.send_notification("Title", "Body") is True
    def test_empty_body(self, notifier):
        assert notifier.send_notification("Title", "") is False
