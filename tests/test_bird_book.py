"""tests/test_bird_book.py"""

from datetime import datetime, timezone

import pytest
from core.types import BirdSighting, RarityLevel
from modules.bird_book import BirdBook

@pytest.fixture
def book():
    return BirdBook()

@pytest.fixture
def sighting():
    return BirdSighting(
        species="American Robin",
        scientific_name="Turdus migratorius",
        confidence=0.9,
        rarity_level=RarityLevel.COMMON,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

class TestBook:
    def test_add_sighting(self, book, sighting):
        book.add_sighting(sighting)
        assert book.species_count == 1
    def test_get_collection(self, book, sighting):
        book.add_sighting(sighting)
        collection = book.get_collection()
        assert len(collection) == 1
        assert collection[0]["species"] == "American Robin"
    def test_get_entry(self, book, sighting):
        book.add_sighting(sighting)
        entry = book.get_entry("American Robin")
        assert entry is not None
        assert entry["total_sightings"] == 1
    def test_get_entry_not_found(self, book):
        assert book.get_entry("Nonexistent") is None
    def test_multiple_sightings_same_species(self, book, sighting):
        book.add_sighting(sighting)
        book.add_sighting(sighting)
        entry = book.get_entry("American Robin")
        assert entry["total_sightings"] == 2
    def test_collection_stats(self, book, sighting):
        book.add_sighting(sighting)
        stats = book.get_collection_stats()
        assert stats["total_species"] == 1
    def test_recent_additions(self, book, sighting):
        book.add_sighting(sighting)
        recent = book.get_recent_additions()
        assert len(recent) == 1
    def test_clear(self, book, sighting):
        book.add_sighting(sighting)
        book.clear()
        assert book.species_count == 0
