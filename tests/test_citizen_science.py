"""tests/test_citizen_science.py"""

from datetime import datetime, timezone

import pytest
from core.types import BirdSighting, RarityLevel
from modules.citizen_science import CitizenScienceUploader

@pytest.fixture
def uploader():
    return CitizenScienceUploader({"mock_mode": True})

@pytest.fixture
def sighting():
    return BirdSighting(
        species="American Robin",
        confidence=0.9,
        rarity_level=RarityLevel.COMMON,
        timestamp=datetime.now(timezone.utc).isoformat(),
        location="Backyard",
    )

class TestUpload:
    def test_mock_upload(self, uploader, sighting):
        assert uploader.upload_sighting(sighting, "ebird") is True
    def test_unknown_platform(self, uploader, sighting):
        assert uploader.upload_sighting(sighting, "unknown") is False
    def test_batch_upload(self, uploader, sighting):
        results = uploader.upload_batch([sighting, sighting, sighting], "ebird")
        assert results["success"] == 3
    def test_upload_stats(self, uploader, sighting):
        uploader.upload_sighting(sighting, "ebird")
        stats = uploader.get_upload_stats()
        assert stats["total_uploads"] == 1
