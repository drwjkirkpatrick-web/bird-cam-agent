"""
modules/thermal_manager.py — Pi thermal management and cooling control.

NOTE: Monitors Pi temperature and controls cooling (fan via GPIO, or
      throttling capture frequency). Prevents thermal throttling and
      hardware damage in outdoor enclosures exposed to sunlight.

WHY: A Pi in a weatherproof enclosure outdoors can overheat — especially
     a Pi 4 or 5 running camera capture + AI identification. Active cooling
     management extends hardware life and prevents performance degradation.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class ThermalManager:
    """
    Manages Pi thermal state and cooling.

    Usage:
        manager = ThermalManager({"mock_mode": True, "fan_gpio_pin": 18})
        temp = manager.get_temperature()
        if manager.should_activate_cooling():
            manager.activate_cooling()
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.mock_mode = self.config.get("mock_mode", True)
        self.fan_gpio_pin = self.config.get("fan_gpio_pin", 18)
        self.temp_threshold = self.config.get("temp_threshold_c", 65)
        self.temp_critical = self.config.get("temp_critical_c", 80)
        self.throttle_threshold = self.config.get("throttle_threshold_c", 75)
        self._fan_active = False
        self._mock_temp = 42.0
        self._throttled = False

    def get_temperature(self) -> float:
        """Get current CPU temperature in Celsius."""
        if self.mock_mode:
            self._mock_temp += (hash(time.time()) % 10 - 5) * 0.2
            self._mock_temp = max(30, min(90, self._mock_temp))
            return round(self._mock_temp, 1)

        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                return round(int(f.read().strip()) / 1000, 1)
        except (FileNotFoundError, PermissionError):
            return self._mock_temp

    def should_activate_cooling(self) -> bool:
        """Check if cooling fan should be activated."""
        return self.get_temperature() >= self.temp_threshold

    def should_throttle(self) -> bool:
        """Check if capture frequency should be reduced."""
        return self.get_temperature() >= self.throttle_threshold

    def is_critical(self) -> bool:
        """Check if temperature is critical."""
        return self.get_temperature() >= self.temp_critical

    def activate_cooling(self) -> bool:
        """Activate the cooling fan via GPIO."""
        if self.mock_mode:
            logger.info("[MOCK] Cooling fan activated")
            self._fan_active = True
            return True

        try:
            import RPi.GPIO as GPIO

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.fan_gpio_pin, GPIO.OUT)
            GPIO.output(self.fan_gpio_pin, GPIO.HIGH)
            self._fan_active = True
            logger.info("Cooling fan activated (GPIO %d)", self.fan_gpio_pin)
            return True
        except ImportError:
            logger.warning("RPi.GPIO not available")
            self._fan_active = True
            return True
        except Exception as e:
            logger.error("Fan control failed: %s", e)
            return False

    def deactivate_cooling(self) -> bool:
        """Deactivate the cooling fan."""
        if self.mock_mode:
            logger.info("[MOCK] Cooling fan deactivated")
            self._fan_active = False
            return True

        try:
            import RPi.GPIO as GPIO

            GPIO.output(self.fan_gpio_pin, GPIO.LOW)
            self._fan_active = False
            return True
        except Exception:
            self._fan_active = False
            return True

    def auto_manage(self) -> dict[str, Any]:
        """
        Automatically manage cooling based on temperature.

        Returns current thermal status dict.
        """
        temp = self.get_temperature()

        if temp >= self.temp_threshold and not self._fan_active:
            self.activate_cooling()
        elif temp < self.temp_threshold - 5 and self._fan_active:
            self.deactivate_cooling()

        if temp >= self.throttle_threshold:
            self._throttled = True
        elif temp < self.throttle_threshold - 5:
            self._throttled = False

        return self.get_status()

    def get_status(self) -> dict[str, Any]:
        """Return thermal management status."""
        temp = self.get_temperature()
        return {
            "temperature_c": temp,
            "fan_active": self._fan_active,
            "throttled": self._throttled,
            "cooling_threshold": self.temp_threshold,
            "critical_threshold": self.temp_critical,
            "is_critical": temp >= self.temp_critical,
            "status": "critical" if temp >= self.temp_critical else
                      "throttled" if temp >= self.throttle_threshold else
                      "cooling" if self._fan_active else "normal",
        }

    @property
    def fan_active(self) -> bool:
        return self._fan_active

    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        if self._fan_active:
            self.deactivate_cooling()


__all__ = ["ThermalManager"]
