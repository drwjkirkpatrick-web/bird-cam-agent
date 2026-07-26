"""tests/test_species_tracker.py — Species tracker tests."""

from datetime import datetime, timezone

import pytest

from core.types import BirdSighting, RarityLevel
from modules.species_tracker import SpeciesTracker


@pytest.fixture
def tracker():
    return SpeciesTracker()


@pytest.fixture
def sighting():
    return BirdSighting(
        species="American Robin",
        confidence=0.9,
        rarity_level=RarityLevel.COMMON,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


class TestAddSighting:
    def test_add_sighting(self, tracker, sighting):
        tracker.add_sighting(sighting)
        assert tracker.species_count == 1
        assert tracker.total_sightings == 1

    def test_add_multiple_same_species(self, tracker, sighting):
        tracker.add_sighting(sighting)
        tracker.add_sighting(sighting)
        assert tracker.species_count == 1
        assert tracker.total_sightings == 2


class TestLifeList:
    def test_empty_life_list(self, tracker):
        assert tracker.get_life_list() == []

    def test_life_list_with_sightings(self, tracker, sighting):
        tracker.add_sighting(sighting)
        s2 = BirdSighting(species="Crow", timestamp=datetime.now(timezone.utc).isoformat())
        tracker.add_sighting(s2)
        life_list = tracker.get_life_list()
        assert len(life_list) == 2

    def test_check_lifer(self, tracker, sighting):
        assert tracker.check_lifer(sighting) is True
        tracker.add_sighting(sighting)
        assert tracker.check_lifer(sighting) is False


class TestDiversity:
    def test_empty_diversity(self, tracker):
        metrics = tracker.get_diversity_metrics()
        assert metrics["species_richness"] == 0

    def test_diversity_with_data(self, tracker, sighting):
        tracker.add_sighting(sighting)
        s2 = BirdSighting(species="Crow", timestamp=datetime.now(timezone.utc).isoformat())
        tracker.add_sighting(s2)
        metrics = tracker.get_diversity_metrics()
        assert metrics["species_richness"] == 2
        assert metrics["shannon_index"] > 0

    def test_evenness_single_species(self, tracker, sighting):
        tracker.add_sighting(sighting)
        metrics = tracker.get_diversity_metrics()
        assert metrics["evenness"] == 0.0


class TestRarest:
    def test_rarest_species(self, tracker):
        common = BirdSighting(species="Robin", rarity_level=RarityLevel.COMMON,
                              timestamp=datetime.now(timezone.utc).isoformat())
        rare = BirdSighting(species="Owl", rarity_level=RarityLevel.RARE,
                           timestamp=datetime.now(timezone.utc).isoformat())
        tracker.add_sighting(common)
        tracker.add_sighting(rare)
        assert tracker.get_rarest_species_seen() == "Owl"

    def test_no_sightings(self, tracker):
        assert tracker.get_rarest_species_seen() is None
