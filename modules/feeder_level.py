"""
modules/feeder_level.py — Bird seed/food level monitoring.

NOTE: Monitors the seed level in the bird feeder using an ultrasonic distance
      sensor (HC-SR04) or IR distance sensor. Alerts when the feeder needs
      refilling.

WHY: Smart feeders monitor food levels. Nobody wants to discover the feeder
     has been empty for days — the birds stopped visiting and you missed
     sightings. This module sends an alert when seed runs low.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class FeederLevelMonitor:
    """
    Monitors bird feeder seed level.

    Usage:
        monitor = FeederLevelMonitor({"mock_mode": True, "full_distance_cm": 5, "empty_distance_cm": 25})
        level = monitor.get_level()
        if level < 20:
            monitor.send_refill_alert()
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.mock_mode = self.config.get("mock_mode", True)
        self.sensor_pin = self.config.get("sensor_pin", 18)
        self.echo_pin = self.config.get("echo_pin", 24)
        self.full_distance_cm = self.config.get("full_distance_cm", 5)
        self.empty_distance_cm = self.config.get("empty_distance_cm", 25)
        self.low_threshold_pct = self.config.get("low_threshold_pct", 20)
        self._mock_level = 75.0
        self._alert_sent = False

    def get_level(self) -> float:
        """
        Get the current seed level as a percentage (0-100).

        100 = full, 0 = empty.
        """
        if self.mock_mode:
            return self._get_mock_level()

        distance = self._read_distance()
        if distance is None:
            return -1

        # NOTE: Closer distance = fuller feeder (sensor is at top, looking down)
        if distance <= self.full_distance_cm:
            return 100.0
        elif distance >= self.empty_distance_cm:
            return 0.0
        else:
            range_cm = self.empty_distance_cm - self.full_distance_cm
            return ((self.empty_distance_cm - distance) / range_cm) * 100

    def _get_mock_level(self) -> float:
        """Simulate slowly draining feeder."""
        self._mock_level = max(0, self._mock_level - 0.1)
        return round(self._mock_level, 1)

    def _read_distance(self) -> float | None:
        """Read distance from ultrasonic sensor."""
        try:
            import RPi.GPIO as GPIO

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.sensor_pin, GPIO.OUT)
            GPIO.setup(self.echo_pin, GPIO.IN)

            GPIO.output(self.sensor_pin, True)
            time.sleep(0.00001)
            GPIO.output(self.sensor_pin, False)

            start = time.time()
            timeout = start + 1
            while GPIO.input(self.echo_pin) == 0 and time.time() < timeout:
                start = time.time()
            while GPIO.input(self.echo_pin) == 1 and time.time() < timeout:
                end = time.time()

            elapsed = end - start
            distance = (elapsed * 34300) / 2  # Speed of sound / 2 (round trip)
            return round(distance, 1)
        except ImportError:
            logger.warning("RPi.GPIO not available — using mock")
            return None
        except Exception as e:
            logger.error("Distance sensor read failed: %s", e)
            return None

    def is_low(self) -> bool:
        """Check if seed level is below the low threshold."""
        return self.get_level() < self.low_threshold_pct

    def should_send_alert(self) -> bool:
        """Check if a refill alert should be sent."""
        level = self.get_level()
        if level < self.low_threshold_pct:
            if not self._alert_sent:
                self._alert_sent = True
                return True
        elif level > self.low_threshold_pct + 20:
            self._alert_sent = False
        return False

    def get_status(self) -> dict[str, Any]:
        """Return feeder level status."""
        level = self.get_level()
        return {
            "level_pct": level,
            "is_low": level < self.low_threshold_pct,
            "status": "full" if level > 70 else "medium" if level > 30 else "low" if level > 10 else "empty",
            "low_threshold": self.low_threshold_pct,
        }


__all__ = ["FeederLevelMonitor"]
