"""tests/test_wifi_messenger.py — WiFi messenger tests."""

import time
from datetime import datetime, timezone

import pytest

from core.types import BirdSighting, RarityLevel
from modules.wifi_messenger import WiFiMessenger


@pytest.fixture
def mock_config():
    return {"mock_mode": True, "cooldown_minutes": 30}


@pytest.fixture
def messenger(mock_config):
    return WiFiMessenger(mock_config)


@pytest.fixture
def rare_sighting():
    return BirdSighting(
        species="Snowy Owl",
        scientific_name="Bubo scandiacus",
        confidence=0.95,
        rarity_level=RarityLevel.RARE,
        timestamp=datetime.now(timezone.utc).isoformat(),
        location="Backyard feeder",
    )


class TestSendAlert:
    def test_send_alert_mock(self, messenger, rare_sighting):
        results = messenger.send_rare_bird_alert(rare_sighting)
        assert "mock" in results
        assert results["mock"] is True
        assert messenger.sent_count == 1

    def test_format_alert_contains_species(self, messenger, rare_sighting):
        body = messenger._format_alert(rare_sighting)
        assert "Snowy Owl" in body
        assert "Rare" in body

    def test_format_alert_contains_location(self, messenger, rare_sighting):
        body = messenger._format_alert(rare_sighting)
        assert "Backyard feeder" in body


class TestRateLimiting:
    def test_rate_limit_prevents_duplicate(self, messenger, rare_sighting):
        assert messenger.send_rare_bird_alert(rare_sighting)
        # Second alert for same species should be rate-limited
        results = messenger.send_rare_bird_alert(rare_sighting)
        assert results == {}  # empty = rate limited
        assert messenger.sent_count == 1

    def test_rate_limit_allows_different_species(self, messenger, rare_sighting):
        messenger.send_rare_bird_alert(rare_sighting)
        other = BirdSighting(
            species="Peregrine Falcon",
            rarity_level=RarityLevel.RARE,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        results = messenger.send_rare_bird_alert(other)
        assert "mock" in results
        assert messenger.sent_count == 2

    def test_rate_limit_allows_after_cooldown(self, messenger):
        messenger._cooldown_seconds = 0.1
        sighting = BirdSighting(
            species="Rare Bird",
            rarity_level=RarityLevel.RARE,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        messenger.send_rare_bird_alert(sighting)
        time.sleep(0.15)
        results = messenger.send_rare_bird_alert(sighting)
        assert "mock" in results
        assert messenger.sent_count == 2

    def test_clear_rate_limits(self, messenger, rare_sighting):
        messenger.send_rare_bird_alert(rare_sighting)
        messenger.clear_rate_limits()
        results = messenger.send_rare_bird_alert(rare_sighting)
        assert "mock" in results


class TestSend:
    def test_send_message_mock(self, messenger):
        results = messenger.send_message("Test message")
        assert "mock" in results
        assert results["mock"] is True

    def test_test_notification(self, messenger):
        results = messenger.test_notification()
        assert "mock" in results
        assert results["mock"] is True


class TestEnabledChannels:
    def test_mock_enabled_by_default(self, messenger):
        assert "mock" in messenger.enabled_channels

    def test_telegram_not_enabled_without_token(self):
        m = WiFiMessenger({"mock_mode": True})
        assert "telegram" not in m.enabled_channels

    def test_telegram_enabled_with_config(self):
        m = WiFiMessenger({
            "mock_mode": False,
            "telegram_bot_token": "test_token",
            "telegram_chat_id": "12345",
        })
        assert "telegram" in m.enabled_channels