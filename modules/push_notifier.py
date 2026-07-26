"""
modules/push_notifier.py — Mobile push notification alerts.

NOTE: Sends push notifications to mobile devices via free services:
      Pushover, Pushbullet, and ntfy.sh. These work over WiFi and don't
      require SMS or a paid provider.

WHY: Birdfy and Bird Buddy send push notifications to a phone app. While
     we don't have a native app, these push services provide the same
     instant-alert experience for free.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from core.types import BirdSighting

logger = logging.getLogger(__name__)


class PushNotifier:
    """
    Push notification system for rare bird alerts.

    Usage:
        notifier = PushNotifier({
            "provider": "ntfy",
            "ntfy_topic": "my-bird-cam",
            "mock_mode": True,
        })
        notifier.send_rare_bird_alert(sighting)
    """

    PROVIDERS = ["pushover", "pushbullet", "ntfy", "mock"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.provider = self.config.get("provider", "mock")
        self.mock_mode = self.config.get("mock_mode", True)
        self._sent_count = 0
        self._last_alert: dict[str, float] = {}
        self._cooldown_seconds = self.config.get("cooldown_minutes", 30) * 60

    def send_rare_bird_alert(self, sighting: BirdSighting) -> bool:
        """Send a push notification for a rare bird sighting."""
        if self._is_rate_limited(sighting.species):
            return False
        title = f"BIRD ALERT: {sighting.species}"
        body = self._format_alert(sighting)
        success = self.send_notification(title, body)
        if success:
            self._last_alert[sighting.species.lower()] = time.time()
            self._sent_count += 1
        return success

    def send_notification(self, title: str, body: str) -> bool:
        """Send a push notification via the configured provider."""
        if not body or not body.strip():
            return False

        provider = "mock" if self.mock_mode else self.provider

        if provider == "mock":
            return self._send_mock(title, body)
        elif provider == "pushover":
            return self._send_pushover(title, body)
        elif provider == "pushbullet":
            return self._send_pushbullet(title, body)
        elif provider == "ntfy":
            return self._send_ntfy(title, body)
        return False

    def _format_alert(self, sighting: BirdSighting) -> str:
        """Format the alert body."""
        rarity = sighting.rarity_level.value.replace("_", " ").title()
        msg = f"A {sighting.species} ({rarity}) was spotted at your feeder!"
        if sighting.scientific_name:
            msg += f"\nScientific: {sighting.scientific_name}"
        if sighting.location:
            msg += f"\nLocation: {sighting.location}"
        return msg

    def _send_pushover(self, title: str, body: str) -> bool:
        """Send via Pushover API."""
        token = self.config.get("pushover_token", "")
        user = self.config.get("pushover_user", "")
        if not token or not user:
            return False
        try:
            url = "https://api.pushover.net/1/messages.json"
            data = urllib.parse.urlencode({
                "token": token, "user": user, "title": title, "message": body,
            }).encode()
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error("Pushover failed: %s", e)
            return False

    def _send_pushbullet(self, title: str, body: str) -> bool:
        """Send via Pushbullet API."""
        token = self.config.get("pushbullet_token", "")
        if not token:
            return False
        try:
            url = "https://api.pushbullet.com/v2/pushes"
            payload = json.dumps({"type": "note", "title": title, "body": body}).encode()
            headers = {"Access-Token": token, "Content-Type": "application/json"}
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error("Pushbullet failed: %s", e)
            return False

    def _send_ntfy(self, title: str, body: str) -> bool:
        """Send via ntfy.sh (free, no auth needed)."""
        topic = self.config.get("ntfy_topic", "")
        if not topic:
            return False
        try:
            url = f"https://ntfy.sh/{topic}"
            req = urllib.request.Request(url, data=body.encode(),
                                         headers={"Title": title}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error("ntfy failed: %s", e)
            return False

    def _send_mock(self, title: str, body: str) -> bool:
        """Mock push notification for testing."""
        logger.info("[MOCK PUSH] %s: %s", title, body[:80])
        print(f"\n[MOCK PUSH] {title}\n  {body}\n")
        return True

    def _is_rate_limited(self, species: str) -> bool:
        key = species.lower()
        last = self._last_alert.get(key)
        if last is None:
            return False
        return (time.time() - last) < self._cooldown_seconds

    def clear_rate_limits(self) -> None:
        self._last_alert.clear()

    def test_notification(self) -> bool:
        """Send a test push notification."""
        self._last_alert.clear()
        return self.send_notification("Bird Cam Test", "Test notification from your bird cam!")

    @property
    def sent_count(self) -> int:
        return self._sent_count


__all__ = ["PushNotifier"]
