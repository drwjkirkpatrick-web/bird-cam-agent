"""tests/test_daily_report.py — Daily report tests."""

from datetime import datetime, timezone

import pytest

from core.types import BirdSighting, RarityLevel
from modules.daily_report import DailyReport


@pytest.fixture
def report_gen():
    return DailyReport()


@pytest.fixture
def sightings():
    return [
        BirdSighting(species="American Robin", confidence=0.9,
                     rarity_level=RarityLevel.COMMON,
                     timestamp="2026-07-25T08:00:00+00:00"),
        BirdSighting(species="Northern Cardinal", confidence=0.85,
                     rarity_level=RarityLevel.UNCOMMON,
                     timestamp="2026-07-25T10:30:00+00:00"),
        BirdSighting(species="Snowy Owl", confidence=0.95,
                     rarity_level=RarityLevel.RARE,
                     timestamp="2026-07-25T14:00:00+00:00"),
        BirdSighting(species="American Robin", confidence=0.88,
                     rarity_level=RarityLevel.COMMON,
                     timestamp="2026-07-25T16:00:00+00:00"),
    ]


class TestGenerate:
    def test_generate_report(self, report_gen, sightings):
        report = report_gen.generate(sightings, date="2026-07-25")
        assert report["date"] == "2026-07-25"
        assert report["total_sightings"] == 4
        assert report["unique_species"] == 3

    def test_empty_report(self, report_gen):
        report = report_gen.generate([], date="2026-07-25")
        assert report["total_sightings"] == 0

    def test_rarity_highlights(self, report_gen, sightings):
        report = report_gen.generate(sightings, date="2026-07-25")
        assert len(report["rarity_highlights"]) == 1
        assert report["rarity_highlights"][0]["species"] == "Snowy Owl"

    def test_most_common(self, report_gen, sightings):
        report = report_gen.generate(sightings, date="2026-07-25")
        assert report["most_common_species"] == "American Robin"

    def test_peak_hour(self, report_gen, sightings):
        report = report_gen.generate(sightings, date="2026-07-25")
        assert report["peak_activity_hour"] in (8, 10, 14, 16)


class TestFormat:
    def test_format_text(self, report_gen, sightings):
        report = report_gen.generate(sightings, date="2026-07-25")
        text = report_gen.format_text(report)
        assert "Bird Cam Daily Report" in text
        assert "American Robin" in text
        assert "Snowy Owl" in text

    def test_format_html(self, report_gen, sightings):
        report = report_gen.generate(sightings, date="2026-07-25")
        html = report_gen.format_html(report)
        assert "<html>" in html
        assert "American Robin" in html
