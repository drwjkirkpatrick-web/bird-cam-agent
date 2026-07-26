"""
modules/gps_tracker.py — GPS location tracking for the bird cam.

NOTE: Reads GPS coordinates from a USB GPS module (NEO-6M, NEO-7M) or
      from a configured static location. Used for sighting records and
      citizen science submissions.

WHY: BirdWeather PUC includes GPS for accurate sighting locations. GPS
     coordinates are required for eBird submissions and improve the
     scientific value of sightings.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GPSReading:
    """A single GPS position reading."""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_m: float = 0.0
    timestamp: str = ""
    satellites: int = 0
    fix_quality: str = "no_fix"


class GPSTracker:
    """
    GPS location tracking for the bird cam.

    Usage:
        tracker = GPSTracker({"mock_mode": True, "static_lat": 45.28, "static_lon": -122.37})
        reading = tracker.get_location()
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.mock_mode = self.config.get("mock_mode", True)
        self.serial_port = self.config.get("serial_port", "/dev/ttyUSB0")
        self.baud_rate = self.config.get("baud_rate", 9600)
        self.static_lat = self.config.get("static_lat")
        self.static_lon = self.config.get("static_lon")
        self.static_alt = self.config.get("static_alt", 0.0)
        self._last_reading: GPSReading | None = None

    def get_location(self) -> GPSReading:
        """Get the current GPS location."""
        if self.static_lat is not None and self.static_lon is not None:
            return GPSReading(
                latitude=self.static_lat,
                longitude=self.static_lon,
                altitude_m=self.static_alt,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                satellites=0,
                fix_quality="static",
            )

        if self.mock_mode:
            return self._mock_location()

        return self._read_gps()

    def _mock_location(self) -> GPSReading:
        """Generate a mock GPS reading."""
        # NOTE: Default to McIver State Park coordinates if no static location
        return GPSReading(
            latitude=45.28 + (hash(time.time()) % 100) / 10000,
            longitude=-122.37 + (hash(time.time() + 1) % 100) / 10000,
            altitude_m=120.0,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            satellites=8,
            fix_quality="mock",
        )

    def _read_gps(self) -> GPSReading:
        """Read from USB GPS module via NMEA sentences."""
        try:
            import serial
            import pynmea2

            with serial.Serial(self.serial_port, self.baud_rate, timeout=5) as ser:
                while True:
                    line = ser.readline().decode("ascii", errors="ignore").strip()
                    if line.startswith("$GPGGA") or line.startswith("$GNGGA"):
                        msg = pynmea2.parse(line)
                        if msg.latitude and msg.longitude:
                            reading = GPSReading(
                                latitude=float(msg.latitude),
                                longitude=float(msg.longitude),
                                altitude_m=float(msg.altitude or 0),
                                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                                satellites=int(msg.num_sats or 0),
                                fix_quality=msg.gps_qual_str,
                            )
                            self._last_reading = reading
                            return reading
            return self._last_reading or self._mock_location()
        except ImportError:
            logger.warning("GPS libraries not available — using mock")
            return self._mock_location()
        except Exception as e:
            logger.error("GPS read failed: %s", e)
            return self._last_reading or self._mock_location()

    def get_location_dict(self) -> dict[str, Any]:
        """Get location as a dictionary for API submissions."""
        r = self.get_location()
        return {
            "latitude": r.latitude,
            "longitude": r.longitude,
            "altitude_m": r.altitude_m,
            "timestamp": r.timestamp,
            "fix_quality": r.fix_quality,
            "satellites": r.satellites,
        }

    @property
    def has_fix(self) -> bool:
        """Check if we have a valid GPS fix."""
        r = self.get_location()
        return r.fix_quality != "no_fix" and r.latitude != 0.0


__all__ = ["GPSTracker", "GPSReading"]
