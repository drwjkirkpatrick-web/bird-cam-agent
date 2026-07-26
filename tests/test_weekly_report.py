"""tests/test_weekly_report.py"""

import pytest
from datetime import datetime, timezone
from core.types import BirdSighting, RarityLevel
from modules.weekly_report import WeeklyReport

@pytest.fixture
def report_gen():
    return WeeklyReport()

@pytest.fixture
def sightings():
    return [
        BirdSighting(species="Robin", confidence=0.9, rarity_level=RarityLevel.COMMON,
                     timestamp="2026-07-22T08:00:00+00:00"),
        BirdSighting(species="Crow", confidence=0.85, rarity_level=RarityLevel.COMMON,
                     timestamp="2026-07-23T10:00:00+00:00"),
        BirdSighting(species="Owl", confidence=0.95, rarity_level=RarityLevel.RARE,
                     timestamp="2026-07-24T14:00:00+00:00"),
    ]

class TestWeeklyReport:
    def test_generate_weekly(self, report_gen, sightings):
        report = report_gen.generate_weekly(sightings, week_start="2026-07-20")
        assert report["total_sightings"] == 3
        assert report["unique_species"] == 3
    def test_empty_week(self, report_gen):
        report = report_gen.generate_weekly([], week_start="2026-07-20")
        assert report["total_sightings"] == 0
    def test_format_text(self, report_gen, sightings):
        report = report_gen.generate_weekly(sightings, week_start="2026-07-20")
        text = report_gen.format_text(report)
        assert "Weekly Report" in text
        assert "Robin" in text
    def test_rare_highlights(self, report_gen, sightings):
        report = report_gen.generate_weekly(sightings, week_start="2026-07-20")
        assert len(report["rare_highlights"]) == 1
    def test_monthly(self, report_gen, sightings):
        report = report_gen.generate_monthly(sightings, 2026, 7)
        assert report["total_sightings"] == 3
