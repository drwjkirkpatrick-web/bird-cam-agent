"""tests/test_sms_notifier.py — SMS notifier tests."""

import time
from datetime import datetime, timezone

import pytest

from core.config import SMSConfig
from core.types import BirdSighting, RarityLevel
from modules.sms_notifier import SMSNotifier


@pytest.fixture
def mock_config():
    return SMSConfig(provider="mock", mock_mode=True, to_number="+15035551234")


@pytest.fixture
def notifier(mock_config):
    return SMSNotifier(mock_config)


@pytest.fixture
def rare_sighting():
    return BirdSighting(
        species="Snowy Owl",
        scientific_name="Bubo scandiacus",
        confidence=0.95,
        photo_path="/data/photos/bird_001.jpg",
        rarity_level=RarityLevel.RARE,
        timestamp=datetime.now(timezone.utc).isoformat(),
        location="Backyard feeder",
    )


@pytest.fixture
def common_sighting():
    return BirdSighting(
        species="American Robin",
        confidence=0.9,
        rarity_level=RarityLevel.COMMON,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


class TestSendAlert:
    def test_send_rare_bird_alert(self, notifier, rare_sighting):
        result = notifier.send_rare_bird_alert(rare_sighting)
        assert result is True
        assert notifier.sent_count == 1

    def test_format_alert_contains_species(self, notifier, rare_sighting):
        body = notifier._format_alert(rare_sighting)
        assert "Snowy Owl" in body
        assert "Rare" in body

    def test_format_alert_contains_scientific_name(self, notifier, rare_sighting):
        body = notifier._format_alert(rare_sighting)
        assert "Bubo scandiacus" in body

    def test_format_alert_contains_location(self, notifier, rare_sighting):
        body = notifier._format_alert(rare_sighting)
        assert "Backyard feeder" in body


class TestRateLimiting:
    def test_rate_limit_prevents_duplicate(self, notifier, rare_sighting):
        # First alert should send
        assert notifier.send_rare_bird_alert(rare_sighting) is True
        # Second alert for same species should be rate-limited
        assert notifier.send_rare_bird_alert(rare_sighting) is False
        assert notifier.sent_count == 1  # only one sent

    def test_rate_limit_allows_different_species(self, notifier, rare_sighting):
        notifier.send_rare_bird_alert(rare_sighting)
        other = BirdSighting(
            species="Peregrine Falcon",
            rarity_level=RarityLevel.RARE,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        assert notifier.send_rare_bird_alert(other) is True
        assert notifier.sent_count == 2

    def test_rate_limit_allows_after_cooldown(self, notifier):
        # Use a very short cooldown for testing
        notifier._cooldown_seconds = 0.1
        sighting = BirdSighting(
            species="Rare Bird",
            rarity_level=RarityLevel.RARE,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        assert notifier.send_rare_bird_alert(sighting) is True
        time.sleep(0.15)
        assert notifier.send_rare_bird_alert(sighting) is True
        assert notifier.sent_count == 2

    def test_clear_rate_limits(self, notifier, rare_sighting):
        notifier.send_rare_bird_alert(rare_sighting)
        notifier.clear_rate_limits()
        # Should be able to send again after clearing
        assert notifier.send_rare_bird_alert(rare_sighting) is True


class TestSend:
    def test_send_message_mock(self, notifier):
        assert notifier.send_message("Test message") is True

    def test_send_empty_message(self, notifier):
        assert notifier.send_message("") is False
        assert notifier.send_message("   ") is False


class TestValidation:
    def test_validate_phone_valid(self, notifier):
        assert notifier._validate_phone("+15035551234") is True
        assert notifier._validate_phone("5035551234") is True

    def test_validate_phone_invalid(self, notifier):
        assert notifier._validate_phone("abc") is False
        assert notifier._validate_phone("") is False
        assert notifier._validate_phone(None) is False

    def test_validate_phone_with_formatting(self, notifier):
        assert notifier._validate_phone("+1 (503) 555-1234") is True


class TestTestNotification:
    def test_test_notification(self, notifier):
        result = notifier.test_notification()
        assert result is True