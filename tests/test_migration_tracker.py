"""tests/test_migration_tracker.py — Migration tracker tests."""

from datetime import datetime, timezone

import pytest

from core.types import BirdSighting, RarityLevel
from modules.migration_tracker import MigrationTracker


@pytest.fixture
def tracker():
    return MigrationTracker()


@pytest.fixture
def spring_sighting():
    return BirdSighting(
        species="Rufous Hummingbird",
        confidence=0.9,
        rarity_level=RarityLevel.UNCOMMON,
        timestamp="2026-04-15T08:00:00+00:00",
    )


class TestAddSighting:
    def test_add_sighting(self, tracker, spring_sighting):
        tracker.add_sighting(spring_sighting)
        assert tracker.tracked_species_count == 1

    def test_add_multiple(self, tracker, spring_sighting):
        tracker.add_sighting(spring_sighting)
        tracker.add_sighting(spring_sighting)
        status = tracker.get_migration_status("Rufous Hummingbird")
        assert status["sighting_count"] == 2


class TestMigrationStatus:
    def test_present_species(self, tracker, spring_sighting):
        tracker.add_sighting(spring_sighting)
        status = tracker.get_migration_status("Rufous Hummingbird")
        assert status["status"] == "present"
        assert status["is_present"] is True

    def test_never_seen(self, tracker):
        status = tracker.get_migration_status("Unknown Bird")
        assert status["status"] == "never_seen"

    def test_mark_absent(self, tracker, spring_sighting):
        tracker.add_sighting(spring_sighting)
        tracker.mark_absent("Rufous Hummingbird", "2026-09-01")
        status = tracker.get_migration_status("Rufous Hummingbird")
        assert status["is_present"] is False


class TestArrivals:
    def test_spring_arrivals(self, tracker, spring_sighting):
        tracker.add_sighting(spring_sighting)
        arrivals = tracker.get_spring_arrivals(year=2026)
        assert len(arrivals) == 1
        assert arrivals[0]["species"] == "Rufous Hummingbird"

    def test_no_spring_arrivals_in_fall(self, tracker):
        fall = BirdSighting(species="Junco", timestamp="2026-10-15T10:00:00+00:00")
        tracker.add_sighting(fall)
        arrivals = tracker.get_spring_arrivals(year=2026)
        assert len(arrivals) == 0


class TestPresent:
    def test_present_list(self, tracker, spring_sighting):
        tracker.add_sighting(spring_sighting)
        present = tracker.get_present_species()
        assert "Rufous Hummingbird" in present


class TestPredictArrival:
    def test_insufficient_data(self, tracker, spring_sighting):
        tracker.add_sighting(spring_sighting)
        result = tracker.predict_arrival("Rufous Hummingbird")
        assert result["prediction"] == "insufficient_data"
