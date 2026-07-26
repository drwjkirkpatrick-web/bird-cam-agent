"""
modules/environmental_sensor.py — Temperature, humidity, pressure readings.

NOTE: Reads environmental data from I2C/SPI sensors (BME280, DHT22, BMP280).
      Useful for correlating bird activity with weather conditions.

WHY: BirdWeather PUC includes environmental sensors. Temperature, humidity,
     and pressure affect bird behavior — having this data alongside sightings
     provides scientific context.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentalReading:
    """A single environmental sensor reading."""
    temperature_c: float = 20.0
    humidity_pct: float = 50.0
    pressure_hpa: float = 1013.0
    dew_point_c: float = 10.0
    timestamp: str = ""
    sensor_type: str = "mock"


class EnvironmentalSensor:
    """
    Reads temperature, humidity, and pressure.

    Usage:
        sensor = EnvironmentalSensor({"mock_mode": True})
        reading = sensor.read()
        print(f"{reading.temperature_c}°C, {reading.humidity_pct}% humidity")
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.mock_mode = self.config.get("mock_mode", True)
        self.sensor_type = self.config.get("sensor_type", "bme280")
        self.i2c_address = self.config.get("i2c_address", 0x76)
        self._mock_temp = 18.0
        self._mock_hum = 55.0
        self._mock_press = 1013.0

    def read(self) -> EnvironmentalReading:
        """Take a single environmental reading."""
        if self.mock_mode:
            return self._mock_read()
        return self._read_hardware()

    def _mock_read(self) -> EnvironmentalReading:
        """Generate realistic environmental readings."""
        hour = time.localtime().tm_hour
        # NOTE: Temperature varies with time of day
        base_temp = 15 + 8 * max(0, 1 - abs(hour - 14) / 7)
        self._mock_temp = base_temp + (hash(time.time()) % 100) / 100.0
        self._mock_hum = 50 + (hash(time.time() + 1) % 30)
        self._mock_press = 1013 + (hash(time.time() + 2) % 20 - 10)

        dew = self._mock_temp - (100 - self._mock_hum) / 5

        return EnvironmentalReading(
            temperature_c=round(self._mock_temp, 1),
            humidity_pct=round(self._mock_hum, 1),
            pressure_hpa=round(self._mock_press, 1),
            dew_point_c=round(dew, 1),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            sensor_type="mock",
        )

    def _read_hardware(self) -> EnvironmentalReading:
        """Read from actual hardware sensor."""
        try:
            import board
            import busio
            import adafruit_bme280

            i2c = busio.I2C(board.SCL, board.SDA)
            sensor = adafruit_bme280.Adafruit_BME280_I2C(i2c, self.i2c_address)

            temp = sensor.temperature
            hum = sensor.humidity
            press = sensor.pressure
            dew = temp - (100 - hum) / 5

            return EnvironmentalReading(
                temperature_c=round(temp, 1),
                humidity_pct=round(hum, 1),
                pressure_hpa=round(press, 1),
                dew_point_c=round(dew, 1),
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                sensor_type=self.sensor_type,
            )
        except ImportError:
            logger.warning("BME280 library not available — using mock")
            return self._mock_read()
        except Exception as e:
            logger.error("Sensor read failed: %s", e)
            return self._mock_read()

    def get_summary(self) -> dict[str, Any]:
        """Return a summary dict of current conditions."""
        r = self.read()
        return {
            "temperature_c": r.temperature_c,
            "humidity_pct": r.humidity_pct,
            "pressure_hpa": r.pressure_hpa,
            "dew_point_c": r.dew_point_c,
            "sensor_type": r.sensor_type,
            "timestamp": r.timestamp,
        }


__all__ = ["EnvironmentalSensor", "EnvironmentalReading"]
