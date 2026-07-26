"""
modules/wifi_messenger.py — WiFi-based messaging for bird alerts.

NOTE: This module provides multiple WiFi-based notification channels as an
      alternative to SMS. When the Pi bird cam is within WiFi range, these
      methods send free messages without needing a cellular plan or Twilio
      account.

WHY: SMS requires a paid provider (Twilio) or a cellular modem. WiFi-based
     messaging is free and works great when the bird cam is deployed near a
     house, cabin, or any location with WiFi access.

SUPPORTED CHANNELS:
  - Telegram Bot: Send messages via Telegram Bot API (free, reliable)
  - Discord Webhook: Send to a Discord channel via webhook URL (free)
  - Email (SMTP): Send email alerts (free with Gmail, etc.)
  - Web Push: HTTP POST to a webhook/IFTTT/n8n endpoint (free)
  - MQTT: Publish to an MQTT broker for home automation integration (free)
  - Mock: Log to console for development/testing
"""

from __future__ import annotations

import json
import logging
import smtplib
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Any

from core.types import BirdSighting, RarityLevel

logger = logging.getLogger(__name__)


class WiFiMessenger:
    """
    WiFi-based multi-channel messaging for bird alerts.

    Usage:
        messenger = WiFiMessenger(config)
        messenger.send_rare_bird_alert(sighting)

    NOTE: Each channel is independent. If one fails, others still attempt.
          The messenger tries all enabled channels and reports success/failure
          per channel.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._sent_count = 0
        self._last_alert: dict[str, float] = {}
        self._cooldown_seconds = self.config.get("cooldown_minutes", 30) * 60

        # Channel configuration
        self._channels: dict[str, bool] = {
            "telegram": bool(self.config.get("telegram_bot_token")),
            "discord": bool(self.config.get("discord_webhook_url")),
            "email": bool(self.config.get("email_to")),
            "webhook": bool(self.config.get("webhook_url")),
            "mqtt": bool(self.config.get("mqtt_broker")),
            "mock": self.config.get("mock_mode", True),
        }

    def send_rare_bird_alert(self, sighting: BirdSighting) -> dict[str, bool]:
        """
        Send a rare bird alert via all enabled WiFi channels.

        Returns a dict of {channel_name: success_bool}.
        """
        if self._is_rate_limited(sighting.species):
            logger.info("Rate-limited alert for %s — skipping", sighting.species)
            return {}

        body = self._format_alert(sighting)
        results: dict[str, bool] = {}

        if self._channels.get("telegram"):
            results["telegram"] = self._send_telegram(body)

        if self._channels.get("discord"):
            results["discord"] = self._send_discord(body)

        if self._channels.get("email"):
            results["email"] = self._send_email(body)

        if self._channels.get("webhook"):
            results["webhook"] = self._send_webhook(body, sighting)

        if self._channels.get("mqtt"):
            results["mqtt"] = self._send_mqtt(body, sighting)

        if self._channels.get("mock"):
            results["mock"] = self._send_mock(body)

        # If any channel succeeded, record the alert time
        if any(results.values()):
            self._last_alert[sighting.species.lower()] = time.time()
            self._sent_count += 1
            logger.info("Rare bird alert sent for %s via: %s", sighting.species,
                        ", ".join(k for k, v in results.items() if v))

        return results

    def send_message(self, body: str) -> dict[str, bool]:
        """Send a generic message via all enabled channels."""
        results: dict[str, bool] = {}

        if self._channels.get("telegram"):
            results["telegram"] = self._send_telegram(body)
        if self._channels.get("discord"):
            results["discord"] = self._send_discord(body)
        if self._channels.get("email"):
            results["email"] = self._send_email(body)
        if self._channels.get("webhook"):
            results["webhook"] = self._send_webhook(body, None)
        if self._channels.get("mqtt"):
            results["mqtt"] = self._send_mqtt(body, None)
        if self._channels.get("mock"):
            results["mock"] = self._send_mock(body)

        return results

    def _format_alert(self, sighting: BirdSighting) -> str:
        """Format the rare bird alert message."""
        rarity_str = sighting.rarity_level.value.replace("_", " ").title()
        ts = sighting.timestamp
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            ts_str = dt.strftime("%b %d, %I:%M %p")
        except (ValueError, AttributeError):
            ts_str = ts

        message = f"BIRD ALERT: A {sighting.species} ({rarity_str}) was spotted at {ts_str}"
        if sighting.scientific_name:
            message += f"\nScientific: {sighting.scientific_name}"
        if sighting.location:
            message += f"\nLocation: {sighting.location}"
        if sighting.photo_path:
            message += f"\nPhoto: {sighting.photo_path}"
        return message

    # --- Telegram Bot ---

    def _send_telegram(self, body: str) -> bool:
        """Send via Telegram Bot API."""
        token = self.config.get("telegram_bot_token", "")
        chat_id = self.config.get("telegram_chat_id", "")

        if not token or not chat_id:
            logger.warning("Telegram config incomplete")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": body,
            "parse_mode": "HTML",
        }).encode()

        try:
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    logger.info("Telegram alert sent")
                    return True
                return False
        except Exception as e:
            logger.error("Telegram send failed: %s", e)
            return False

    # --- Discord Webhook ---

    def _send_discord(self, body: str) -> bool:
        """Send via Discord webhook."""
        webhook_url = self.config.get("discord_webhook_url", "")

        if not webhook_url:
            return False

        payload = json.dumps({"content": body}).encode()
        headers = {"Content-Type": "application/json"}

        try:
            req = urllib.request.Request(webhook_url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 204):
                    logger.info("Discord alert sent")
                    return True
                return False
        except Exception as e:
            logger.error("Discord send failed: %s", e)
            return False

    # --- Email (SMTP) ---

    def _send_email(self, body: str) -> bool:
        """Send via SMTP email."""
        smtp_host = self.config.get("smtp_host", "smtp.gmail.com")
        smtp_port = self.config.get("smtp_port", 587)
        smtp_user = self.config.get("smtp_user", "")
        smtp_pass = self.config.get("smtp_password", "")
        email_to = self.config.get("email_to", "")
        email_from = self.config.get("email_from", smtp_user)

        if not email_to or not smtp_user:
            logger.warning("Email config incomplete")
            return False

        try:
            msg = MIMEText(body)
            msg["Subject"] = "Bird Cam Alert: Rare Bird Detected"
            msg["From"] = email_from
            msg["To"] = email_to

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(email_from, [email_to], msg.as_string())

            logger.info("Email alert sent to %s", email_to)
            return True
        except Exception as e:
            logger.error("Email send failed: %s", e)
            return False

    # --- Generic Webhook (IFTTT, n8n, Home Assistant, etc.) ---

    def _send_webhook(self, body: str, sighting: BirdSighting | None) -> bool:
        """Send via HTTP POST to a webhook URL."""
        webhook_url = self.config.get("webhook_url", "")

        if not webhook_url:
            return False

        payload: dict[str, Any] = {"message": body}
        if sighting:
            payload["species"] = sighting.species
            payload["rarity"] = sighting.rarity_level.value
            payload["timestamp"] = sighting.timestamp
            payload["photo_path"] = sighting.photo_path

        data = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}

        try:
            req = urllib.request.Request(webhook_url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201, 204):
                    logger.info("Webhook alert sent to %s", webhook_url)
                    return True
                return False
        except Exception as e:
            logger.error("Webhook send failed: %s", e)
            return False

    # --- MQTT (home automation integration) ---

    def _send_mqtt(self, body: str, sighting: BirdSighting | None) -> bool:
        """Publish to an MQTT broker."""
        broker = self.config.get("mqtt_broker", "")
        port = self.config.get("mqtt_port", 1883)
        topic = self.config.get("mqtt_topic", "birdcam/alerts")

        if not broker:
            return False

        try:
            import paho.mqtt.client as mqtt

            client = mqtt.Client()
            client.connect(broker, port, 60)
            client.publish(topic, body)
            client.disconnect()
            logger.info("MQTT alert published to %s", topic)
            return True
        except ImportError:
            logger.warning("paho-mqtt not installed — skipping MQTT channel")
            return False
        except Exception as e:
            logger.error("MQTT send failed: %s", e)
            return False

    # --- Mock ---

    def _send_mock(self, body: str) -> bool:
        """Log the message for development/testing."""
        logger.info("[MOCK WiFi] %s", body)
        print(f"\n[MOCK WiFi] {body}\n")
        return True

    # --- Rate limiting ---

    def _is_rate_limited(self, species: str) -> bool:
        """Check if we're in the cooldown window for this species."""
        key = species.lower()
        last_time = self._last_alert.get(key)
        if last_time is None:
            return False
        return (time.time() - last_time) < self._cooldown_seconds

    def clear_rate_limits(self) -> None:
        """Clear all rate limit tracking (for testing)."""
        self._last_alert.clear()

    def test_notification(self) -> dict[str, bool]:
        """Send a test notification via all enabled channels."""
        test_sighting = BirdSighting(
            species="Test Bird",
            scientific_name="Testus birdius",
            confidence=1.0,
            rarity_level=RarityLevel.RARE,
            timestamp=datetime.now(timezone.utc).isoformat(),
            location="Test Location",
        )
        self._last_alert.clear()
        return self.send_rare_bird_alert(test_sighting)

    @property
    def sent_count(self) -> int:
        """Total number of alerts sent."""
        return self._sent_count

    @property
    def enabled_channels(self) -> list[str]:
        """List of enabled channel names."""
        return [k for k, v in self._channels.items() if v]


__all__ = ["WiFiMessenger"]