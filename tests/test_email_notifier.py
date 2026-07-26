"""tests/test_email_notifier.py — Email notifier tests."""

import time
from datetime import datetime, timezone

import pytest

from core.types import BirdSighting, RarityLevel
from modules.email_notifier import EmailNotifier


@pytest.fixture
def notifier():
    return EmailNotifier({"mock_mode": True, "cooldown_minutes": 30})


@pytest.fixture
def rare_sighting():
    return BirdSighting(
        species="Snowy Owl",
        scientific_name="Bubo scandiacus",
        confidence=0.95,
        rarity_level=RarityLevel.RARE,
        timestamp=datetime.now(timezone.utc).isoformat(),
        location="Backyard",
    )


class TestSendAlert:
    def test_send_alert_mock(self, notifier, rare_sighting):
        assert notifier.send_rare_bird_alert(rare_sighting) is True
        assert notifier.sent_count == 1

    def test_format_alert_contains_species(self, notifier, rare_sighting):
        body = notifier._format_alert(rare_sighting)
        assert "Snowy Owl" in body
        assert "Rare" in body

    def test_format_alert_contains_location(self, notifier, rare_sighting):
        body = notifier._format_alert(rare_sighting)
        assert "Backyard" in body


class TestRateLimiting:
    def test_rate_limit(self, notifier, rare_sighting):
        notifier.send_rare_bird_alert(rare_sighting)
        assert notifier.send_rare_bird_alert(rare_sighting) is False

    def test_clear_rate_limits(self, notifier, rare_sighting):
        notifier.send_rare_bird_alert(rare_sighting)
        notifier.clear_rate_limits()
        assert notifier.send_rare_bird_alert(rare_sighting) is True


class TestDailyReport:
    def test_send_daily_report(self, notifier):
        assert notifier.send_daily_report("Test report", "2026-07-25") is True


class TestTestNotification:
    def test_test_notification(self, notifier):
        assert notifier.test_notification() is True
