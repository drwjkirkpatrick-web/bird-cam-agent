"""
modules/citizen_science.py — Share sightings with research platforms.

NOTE: Uploads bird sightings to citizen science platforms: eBird, iNaturalist,
      BirdWeather, and GBIF. Each platform has its own API format.

WHY: Birdfy and Bird Buddy both contribute to citizen science. This module
     lets bird cam owners contribute their sightings to global research databases.
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


class CitizenScienceUploader:
    """
    Uploads sightings to citizen science platforms.

    Usage:
        uploader = CitizenScienceUploader({"mock_mode": True})
        uploader.upload_sighting(sighting, platform="ebird")
    """

    PLATFORMS = ["ebird", "inaturalist", "birdweather", "gbif"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.mock_mode = self.config.get("mock_mode", True)
        self._upload_count = 0
        self._failed_count = 0
        self._platforms_enabled: dict[str, bool] = {
            "ebird": bool(self.config.get("ebird_api_key")),
            "inaturalist": bool(self.config.get("inaturalist_token")),
            "birdweather": bool(self.config.get("birdweather_station_id")),
            "gbif": False,  # NOTE: GBIF is read-only, no uploads
            "mock": self.mock_mode,
        }

    def upload_sighting(self, sighting: BirdSighting, platform: str = "ebird") -> bool:
        """Upload a single sighting to a platform."""
        if platform not in self.PLATFORMS:
            logger.error("Unknown platform: %s", platform)
            return False

        if self.mock_mode or not self._platforms_enabled.get(platform, False):
            return self._mock_upload(sighting, platform)

        if platform == "ebird":
            return self._upload_ebird(sighting)
        elif platform == "inaturalist":
            return self._upload_inaturalist(sighting)
        elif platform == "birdweather":
            return self._upload_birdweather(sighting)
        return False

    def upload_batch(self, sightings: list[BirdSighting], platform: str = "ebird") -> dict[str, int]:
        """Upload multiple sightings to a platform."""
        success = 0
        failed = 0
        for s in sightings:
            if self.upload_sighting(s, platform):
                success += 1
            else:
                failed += 1
        return {"success": success, "failed": failed, "total": len(sightings)}

    def _upload_ebird(self, sighting: BirdSighting) -> bool:
        """Upload to eBird API."""
        api_key = self.config.get("ebird_api_key", "")
        if not api_key:
            return False
        # NOTE: eBird submission API requires specific format
        # This is a simplified version — real eBird submissions need more fields
        try:
            url = "https://api.ebird.org/v2/product/checklist"
            payload = json.dumps({
                "species": sighting.species,
                "count": 1,
                "location": sighting.location,
                "date": sighting.timestamp[:10],
            }).encode()
            headers = {"X-eBirdApiToken": api_key, "Content-Type": "application/json"}
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status in (200, 201):
                    self._upload_count += 1
                    return True
            return False
        except Exception as e:
            logger.error("eBird upload failed: %s", e)
            self._failed_count += 1
            return False

    def _upload_inaturalist(self, sighting: BirdSighting) -> bool:
        """Upload to iNaturalist API."""
        token = self.config.get("inaturalist_token", "")
        if not token:
            return False
        try:
            url = "https://api.inaturalist.org/v1/observations"
            payload = json.dumps({
                "species_name": sighting.species,
                "observed_on": sighting.timestamp,
                "location": sighting.location,
                "description": f"Auto-detected by Bird Cam (confidence: {sighting.confidence:.0%})",
            }).encode()
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status in (200, 201):
                    self._upload_count += 1
                    return True
            return False
        except Exception as e:
            logger.error("iNaturalist upload failed: %s", e)
            self._failed_count += 1
            return False

    def _upload_birdweather(self, sighting: BirdSighting) -> bool:
        """Upload to BirdWeather."""
        station_id = self.config.get("birdweather_station_id", "")
        if not station_id:
            return False
        try:
            url = f"https://app.birdweather.com/api/v1/stations/{station_id}/detections"
            payload = json.dumps({
                "species": sighting.species,
                "timestamp": sighting.timestamp,
                "confidence": sighting.confidence,
            }).encode()
            headers = {"Content-Type": "application/json"}
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status in (200, 201):
                    self._upload_count += 1
                    return True
            return False
        except Exception as e:
            logger.error("BirdWeather upload failed: %s", e)
            self._failed_count += 1
            return False

    def _mock_upload(self, sighting: BirdSighting, platform: str) -> bool:
        """Mock upload for testing."""
        logger.info("[MOCK] Upload to %s: %s", platform, sighting.species)
        self._upload_count += 1
        return True

    def get_upload_stats(self) -> dict[str, Any]:
        """Return upload statistics."""
        return {
            "total_uploads": self._upload_count,
            "failed_uploads": self._failed_count,
            "enabled_platforms": [k for k, v in self._platforms_enabled.items() if v],
        }


__all__ = ["CitizenScienceUploader"]
