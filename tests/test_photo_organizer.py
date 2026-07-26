"""tests/test_photo_organizer.py — Photo organizer tests."""

import os
import tempfile

import pytest

from core.types import BirdSighting, RarityLevel
from modules.photo_organizer import PhotoOrganizer


@pytest.fixture
def organizer(tmp_path):
    return PhotoOrganizer(base_dir=str(tmp_path / "photos"))


@pytest.fixture
def photo(tmp_path):
    """Create a temp photo file."""
    photo_dir = tmp_path / "raw"
    photo_dir.mkdir()
    photo_path = photo_dir / "bird_001.jpg"
    photo_path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9")
    return str(photo_path)


@pytest.fixture
def sighting(photo):
    return BirdSighting(
        species="American Robin",
        confidence=0.9,
        rarity_level=RarityLevel.COMMON,
        photo_path=photo,
        timestamp="2026-07-25T10:00:00+00:00",
    )


class TestOrganize:
    def test_organize_photo(self, organizer, sighting):
        new_path = organizer.organize_photo(sighting)
        assert new_path is not None
        assert os.path.exists(new_path)
        assert "American_Robin" in new_path

    def test_organize_missing_photo(self, organizer):
        s = BirdSighting(species="Test", photo_path="/nonexistent.jpg",
                        timestamp="2026-01-01T00:00:00+00:00")
        assert organizer.organize_photo(s) is None

    def test_organize_creates_directory_structure(self, organizer, sighting):
        new_path = organizer.organize_photo(sighting)
        assert "2026" in new_path
        assert "07" in new_path


class TestStorageStats:
    def test_empty_stats(self, organizer):
        stats = organizer.get_storage_stats()
        assert stats["total_files"] == 0

    def test_stats_with_photos(self, organizer, sighting):
        organizer.organize_photo(sighting)
        stats = organizer.get_storage_stats()
        assert stats["total_files"] == 1
        assert stats["total_size_bytes"] > 0


class TestSearch:
    def test_search_by_species(self, organizer, sighting):
        organizer.organize_photo(sighting)
        results = organizer.search_photos(species="American Robin")
        assert len(results) == 1

    def test_search_no_results(self, organizer, sighting):
        organizer.organize_photo(sighting)
        results = organizer.search_photos(species="Nonexistent")
        assert len(results) == 0


class TestCleanup:
    def test_cleanup_old_photos(self, organizer, sighting):
        organizer.organize_photo(sighting)
        # max_age_days=0 should delete everything
        deleted = organizer.cleanup_old_photos(max_age_days=0)
        assert deleted >= 1
