"""
modules/sms_notifier.py — SMS alerts for rare bird sightings.

NOTE: This module sends text messages to the bird cam owner when a rare
      bird is identified. It supports three providers:
      - "twilio":         Twilio SMS API
      - "hermes_gateway": Hermes Agent's built-in SMS gateway
      - "mock":           logs the message, returns success (for dev/test)

WHY: Real-time rare bird alerts are the key feature. A birdwatcher wants
     to know the moment a rare species lands at the feeder so they can
     look or come home. SMS is the most reliable push channel — it works
     on any phone, doesn't require an app, and gets attention.

DESIGN: Rate limiting prevents alert fatigue. If the same species visits
        repeatedly, the owner only gets one alert per cooldown window
        (default 30 minutes). Different rare species each get their own
        alert immediately.
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

from core.config import SMSConfig
from core.types import BirdSighting, RarityLevel

logger = logging.getLogger(__name__)


class SMSNotifier:
    """
    SMS notification system for rare bird alerts.

    Usage:
        notifier = SMSNotifier(config.sms)
        if notifier.send_rare_bird_alert(sighting):
            print("Alert sent!")
    """

    def __init__(self, config: SMSConfig):
        self.config = config
        # NOTE: Track last alert time per species for rate limiting
        self._last_alert: dict[str, float] = {}
        self._cooldown_seconds = config.cooldown_minutes * 60
        self._sent_count = 0

    def send_rare_bird_alert(self, sighting: BirdSighting) -> bool:
        """
        Send an SMS alert about a rare bird sighting.

        Returns True if the alert was sent, False if rate-limited or failed.
        """
        # NOTE: Rate limit check — skip if we already alerted for this species
        if self._is_rate_limited(sighting.species):
            logger.info(
                "Rate-limited alert for %s — skipping (cooldown %dm)",
                sighting.species,
                self.config.cooldown_minutes,
            )
            return False

        body = self._format_alert(sighting)
        success = self.send_message(body)

        if success:
            self._last_alert[sighting.species.lower()] = time.time()
            self._sent_count += 1
            logger.info("Rare bird alert sent for %s", sighting.species)

        return success

    def send_message(self, body: str, to_number: str | None = None) -> bool:
        """
        Send an SMS message.

        Returns True on success, False on failure.
        """
        if not body or not body.strip():
            logger.warning("Empty message body — not sending")
            return False

        recipient = to_number or self.config.to_number
        if not recipient and not self._is_mock_mode():
            logger.warning("No recipient phone number configured")
            return False

        mode = self._get_mode()

        if mode == "mock":
            return self.mock_send(body, recipient)
        elif mode == "twilio":
            return self._send_twilio(body, recipient)
        elif mode == "hermes_gateway":
            return self._send_hermes_gateway(body, recipient)
        else:
            logger.error("Unknown SMS provider: %s", mode)
            return False

    def _format_alert(self, sighting: BirdSighting) -> str:
        """Format the rare bird alert message."""
        rarity_str = sighting.rarity_level.value.replace("_", " ").title()
        # NOTE: Format the timestamp for readability
        ts = sighting.timestamp
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            ts_str = dt.strftime("%b %d, %I:%M %p")
        except (ValueError, AttributeError):
            ts_str = ts

        message = (
            f"BIRD ALERT: A {sighting.species} ({rarity_str}) "
            f"was spotted at {ts_str}"
        )

        if sighting.scientific_name:
            message += f"\nScientific: {sighting.scientific_name}"

        if sighting.location:
            message += f"\nLocation: {sighting.location}"

        if sighting.photo_path:
            message += f"\nPhoto: {sighting.photo_path}"

        # NOTE: SMS length limit is 160 chars for a single segment.
        # Long messages get split but still send. We keep it concise.
        return message

    def _send_twilio(self, body: str, to_number: str) -> bool:
        """Send SMS via Twilio API."""
        # Validate phone number format
        if not self._validate_phone(to_number):
            logger.error("Invalid phone number: %s", to_number)
            return False

        try:
            from twilio.rest import Client
        except ImportError:
            logger.error("twilio library not installed — cannot send SMS")
            return False

        try:
            client = Client(self.config.account_sid, self.config.auth_token)
            message = client.messages.create(
                body=body,
                from_=self.config.from_number,
                to=to_number,
            )
            logger.info("Twilio SMS sent: %s", message.sid)
            return True
        except Exception as e:
            logger.error("Twilio SMS failed: %s", e)
            return False

    def _send_hermes_gateway(self, body: str, to_number: str) -> bool:
        """Send SMS via Hermes Agent's SMS gateway."""
        if not self._validate_phone(to_number):
            logger.error("Invalid phone number: %s", to_number)
            return False

        # NOTE: Hermes CLI can send SMS via the gateway if configured
        cmd = [
            "hermes",
            "chat",
            "-q",
            f"Send an SMS message to {to_number} with this content: {body}",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info("Hermes gateway SMS sent to %s", to_number)
                return True
            else:
                logger.error(
                    "Hermes gateway SMS failed (code %d): %s",
                    result.returncode,
                    result.stderr[:200],
                )
                return False
        except subprocess.TimeoutExpired:
            logger.error("Hermes gateway SMS timed out")
            return False
        except FileNotFoundError:
            logger.error("hermes CLI not found")
            return False
        except Exception as e:
            logger.error("Hermes gateway error: %s", e)
            return False

    def mock_send(self, body: str, to_number: str | None = None) -> bool:
        """Log the SMS message without actually sending it (for testing)."""
        logger.info("[MOCK SMS] To: %s | Body: %s", to_number or "N/A", body)
        print(f"\n[MOCK SMS] To: {to_number or 'N/A'}")
        print(f"  Body: {body}\n")
        return True

    def test_notification(self) -> bool:
        """Send a test SMS notification."""
        test_sighting = BirdSighting(
            species="Test Bird",
            scientific_name="Testus birdius",
            confidence=1.0,
            rarity_level=RarityLevel.RARE,
            timestamp=datetime.now(timezone.utc).isoformat(),
            location="Test Location",
            notes="This is a test notification",
        )
        # NOTE: Bypass rate limiting for the test
        self._last_alert.clear()
        return self.send_rare_bird_alert(test_sighting)

    def _is_rate_limited(self, species: str) -> bool:
        """Check if we're still in the cooldown window for this species."""
        key = species.lower()
        last_time = self._last_alert.get(key)
        if last_time is None:
            return False
        elapsed = time.time() - last_time
        return elapsed < self._cooldown_seconds

    def _is_mock_mode(self) -> bool:
        """Check if we're in mock mode."""
        return self.config.mock_mode or self.config.provider == "mock"

    def _get_mode(self) -> str:
        """Get the effective SMS mode."""
        if self._is_mock_mode():
            return "mock"
        return self.config.provider

    def _validate_phone(self, number: str) -> bool:
        """Validate a phone number (basic E.164 format check)."""
        if not number:
            return False
        # NOTE: E.164 format: + followed by 1-15 digits
        cleaned = re.sub(r"[\s\-\(\)]", "", number)
        return bool(re.match(r"^\+?\d{10,15}$", cleaned))

    @property
    def sent_count(self) -> int:
        """Total number of SMS alerts sent."""
        return self._sent_count

    def clear_rate_limits(self) -> None:
        """Clear all rate limit tracking (for testing)."""
        self._last_alert.clear()