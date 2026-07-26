"""tests/test_feeder_monitor.py — Feeder monitor tests."""

from datetime import datetime, timezone

import pytest

from core.types import BirdSighting, RarityLevel
from modules.feeder_monitor import FeederMonitor


@pytest.fixture
def monitor():
    return FeederMonitor()


@pytest.fixture
def sighting():
    return BirdSighting(
        species="American Robin",
        confidence=0.9,
        rarity_level=RarityLevel.COMMON,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


class TestRecordVisit:
    def test_record_visit(self, monitor, sighting):
        monitor.record_visit(sighting)
        assert monitor.total_visits == 1

    def test_record_multiple(self, monitor, sighting):
        for _ in range(5):
            monitor.record_visit(sighting)
        assert monitor.total_visits == 5


class TestStats:
    def test_empty_stats(self, monitor):
        stats = monitor.get_activity_stats()
        assert stats["total_visits"] == 0

    def test_stats_with_visits(self, monitor, sighting):
        monitor.record_visit(sighting)
        monitor.record_visit(sighting)
        stats = monitor.get_activity_stats()
        assert stats["total_visits"] == 2
        assert stats["unique_species"] == 1
        assert stats["most_visited_species"] == "American Robin"

    def test_species_frequency(self, monitor, sighting):
        monitor.record_visit(sighting)
        monitor.record_visit(sighting)
        s2 = BirdSighting(species="Crow", timestamp=datetime.now(timezone.utc).isoformat())
        monitor.record_visit(s2)
        freq = monitor.get_species_frequency()
        assert "American Robin" in freq
        assert freq["American Robin"] == 66.7

    def test_recent_visits(self, monitor, sighting):
        monitor.record_visit(sighting)
        recent = monitor.get_recent_visits()
        assert len(recent) == 1
        assert recent[0]["species"] == "American Robin"


class TestClear:
    def test_clear(self, monitor, sighting):
        monitor.record_visit(sighting)
        monitor.clear()
        assert monitor.total_visits == 0
