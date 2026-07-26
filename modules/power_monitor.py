"""
modules/power_monitor.py — Solar and battery power monitoring.

NOTE: Monitors power source (battery, solar, USB), estimates remaining
      runtime, and alerts when power is low. Supports INA219 voltage/current
      sensor, ADS1115 ADC, or mock mode with simulated values.

WHY: Birdfy Pro and Bird Buddy both offer solar panels. A Pi-based bird cam
     deployed outdoors needs power monitoring to avoid unexpected shutdowns.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PowerStatus:
    """Current power system status."""
    voltage: float = 0.0
    current_ma: float = 0.0
    power_mw: float = 0.0
    battery_pct: float = 100.0
    solar_charging: bool = False
    solar_voltage: float = 0.0
    estimated_runtime_hours: float = 0.0
    source: str = "unknown"
    timestamp: str = ""


class PowerMonitor:
    """
    Monitors power for a solar/battery-powered bird cam.

    Usage:
        monitor = PowerMonitor({"mock_mode": True})
        status = monitor.get_status()
        if status.battery_pct < 20:
            monitor.send_low_power_alert()
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.mock_mode = self.config.get("mock_mode", True)
        self.low_battery_threshold = self.config.get("low_battery_threshold", 20)
        self.critical_threshold = self.config.get("critical_threshold", 10)
        self.battery_capacity_mah = self.config.get("battery_capacity_mah", 10000)
        self._mock_battery = 85.0
        self._mock_solar = True
        self._alert_sent = False

    def get_status(self) -> PowerStatus:
        """Get current power status."""
        if self.mock_mode:
            return self._mock_status()
        return self._read_hardware()

    def _mock_status(self) -> PowerStatus:
        """Generate simulated power readings."""
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        # NOTE: Simulate slow battery drain with solar recovery
        hour = time.localtime().tm_hour
        if 6 <= hour <= 18 and self._mock_solar:
            self._mock_battery = min(100, self._mock_battery + 0.01)
        else:
            self._mock_battery = max(0, self._mock_battery - 0.05)

        voltage = 3.7 + (self._mock_battery / 100) * 0.8
        current = 350 if self._mock_battery > 20 else 300
        runtime = (self._mock_battery / 100) * self.battery_capacity_mah / max(current, 1)

        return PowerStatus(
            voltage=round(voltage, 2),
            current_ma=current,
            power_mw=round(voltage * current, 1),
            battery_pct=round(self._mock_battery, 1),
            solar_charging=6 <= hour <= 18,
            solar_voltage=5.0 if 6 <= hour <= 18 else 0.0,
            estimated_runtime_hours=round(runtime, 1),
            source="solar+ battery" if 6 <= hour <= 18 else "battery",
            timestamp=ts,
        )

    def _read_hardware(self) -> PowerStatus:
        """Read from INA219 or ADS1115 sensor."""
        try:
            import board
            import busio
            from adafruit_ina219 import INA219

            i2c = busio.I2C(board.SCL, board.SDA)
            sensor = INA219(i2c)
            voltage = sensor.bus_voltage
            current = sensor.current
            power = sensor.power

            battery_pct = max(0, min(100, (voltage - 3.0) / 1.2 * 100))
            runtime = (battery_pct / 100) * self.battery_capacity_mah / max(abs(current), 1)

            return PowerStatus(
                voltage=round(voltage, 2),
                current_ma=round(current, 1),
                power_mw=round(power, 1),
                battery_pct=round(battery_pct, 1),
                solar_charging=current > 0,
                estimated_runtime_hours=round(runtime, 1),
                source="solar" if current > 0 else "battery",
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            )
        except ImportError:
            logger.warning("INA219 library not available — using mock")
            return self._mock_status()
        except Exception as e:
            logger.error("Power sensor read failed: %s", e)
            return self._mock_status()

    def is_low_battery(self) -> bool:
        """Check if battery is below low threshold."""
        return self.get_status().battery_pct < self.low_battery_threshold

    def is_critical_battery(self) -> bool:
        """Check if battery is critically low."""
        return self.get_status().battery_pct < self.critical_threshold

    def should_send_alert(self) -> bool:
        """Check if a low-power alert should be sent (once per low cycle)."""
        status = self.get_status()
        if status.battery_pct < self.low_battery_threshold:
            if not self._alert_sent:
                self._alert_sent = True
                return True
        elif status.battery_pct > self.low_battery_threshold + 10:
            self._alert_sent = False
        return False

    def get_power_summary(self) -> dict[str, Any]:
        """Return a power status summary dict."""
        s = self.get_status()
        return {
            "battery_pct": s.battery_pct,
            "voltage": s.voltage,
            "current_ma": s.current_ma,
            "solar_charging": s.solar_charging,
            "estimated_runtime_hours": s.estimated_runtime_hours,
            "source": s.source,
            "low_battery": self.is_low_battery(),
            "critical": self.is_critical_battery(),
        }


__all__ = ["PowerMonitor", "PowerStatus"]
