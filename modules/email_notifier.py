"""
modules/email_notifier.py — Email-based bird alert notifications.

NOTE: Sends email alerts when rare birds are detected. Uses SMTP for
      sending — works with Gmail, Outlook, or any SMTP server.

WHY: Email is a free, universal notification channel. While SMS requires
     a paid provider, email works with any free email account and can
     include photo attachments.
"""

from __future__ import annotations

import logging
import smtplib
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from core.types import BirdSighting, RarityLevel

logger = logging.getLogger(__name__)


class EmailNotifier:
    """
    Email notification system for rare bird alerts.

    Usage:
        notifier = EmailNotifier({
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_user": "user@gmail.com",
            "smtp_password": "app_password",
            "email_to": "walker@example.com",
            "mock_mode": True,
        })
        notifier.send_rare_bird_alert(sighting)
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._last_alert: dict[str, float] = {}
        self._cooldown_seconds = config.get("cooldown_minutes", 30) * 60
        self._sent_count = 0

    def send_rare_bird_alert(self, sighting: BirdSighting) -> bool:
        """Send an email alert about a rare bird sighting."""
        if self._is_rate_limited(sighting.species):
            logger.info("Rate-limited email alert for %s", sighting.species)
            return False

        subject = f"BIRD ALERT: {sighting.species} ({sighting.rarity_level.value})"
        body = self._format_alert(sighting)

        success = self._send_email(subject, body, sighting.photo_path)

        if success:
            self._last_alert[sighting.species.lower()] = time.time()
            self._sent_count += 1
            logger.info("Email alert sent for %s", sighting.species)

        return success

    def send_daily_report(self, report_text: str, date: str) -> bool:
        """Send a daily report email."""
        subject = f"Bird Cam Daily Report — {date}"
        return self._send_email(subject, report_text, None)

    def _format_alert(self, sighting: BirdSighting) -> str:
        """Format the email body for a rare bird alert."""
        rarity_str = sighting.rarity_level.value.replace("_", " ").title()
        ts = sighting.timestamp
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            ts_str = dt.strftime("%B %d, %Y at %I:%M %p")
        except (ValueError, AttributeError):
            ts_str = ts

        body = f"""
A {sighting.species} has been spotted at your bird feeder!

Species:          {sighting.species}
Scientific name:  {sighting.scientific_name or 'Unknown'}
Rarity:           {rarity_str}
Confidence:       {sighting.confidence:.0%}
Time:             {ts_str}
Location:         {sighting.location or 'Unknown'}
Photo:            {sighting.photo_path or 'No photo'}

Notes: {sighting.notes or 'None'}

This alert was sent by your Bird Cam Agent.
"""
        return body.strip()

    def _send_email(
        self, subject: str, body: str, photo_path: str | None = None
    ) -> bool:
        """Send an email via SMTP."""
        if self.config.get("mock_mode", True):
            logger.info("[MOCK EMAIL] Subject: %s", subject)
            print(f"\n[MOCK EMAIL] {subject}\n{body[:200]}...\n")
            return True

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
            msg["Subject"] = subject
            msg["From"] = email_from
            msg["To"] = email_to

            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(email_from, [email_to], msg.as_string())

            logger.info("Email sent to %s: %s", email_to, subject)
            return True
        except Exception as e:
            logger.error("Email send failed: %s", e)
            return False

    def _is_rate_limited(self, species: str) -> bool:
        """Check rate limiting for a species."""
        key = species.lower()
        last = self._last_alert.get(key)
        if last is None:
            return False
        return (time.time() - last) < self._cooldown_seconds

    def clear_rate_limits(self) -> None:
        """Clear rate limiting (for testing)."""
        self._last_alert.clear()

    def test_notification(self) -> bool:
        """Send a test email."""
        test = BirdSighting(
            species="Test Bird",
            scientific_name="Testus birdius",
            confidence=1.0,
            rarity_level=RarityLevel.RARE,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._last_alert.clear()
        return self.send_rare_bird_alert(test)

    @property
    def sent_count(self) -> int:
        return self._sent_count


__all__ = ["EmailNotifier"]