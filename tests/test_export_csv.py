"""tests/test_export_csv.py — Data export tests."""

import csv
import json
import os

import pytest

from core.types import BirdSighting, RarityLevel
from modules.export_csv import DataExporter


@pytest.fixture
def exporter():
    return DataExporter()


@pytest.fixture
def sightings():
    return [
        BirdSighting(species="American Robin", confidence=0.9,
                     rarity_level=RarityLevel.COMMON,
                     timestamp="2026-07-25T08:00:00+00:00",
                     location="Backyard"),
        BirdSighting(species="Snowy Owl", confidence=0.95,
                     rarity_level=RarityLevel.RARE,
                     timestamp="2026-07-25T14:00:00+00:00",
                     location="Backyard"),
    ]


class TestExportCSV:
    def test_export_csv(self, exporter, sightings, tmp_path):
        path = str(tmp_path / "test.csv")
        result = exporter.export_csv(sightings, path)
        assert result == path
        assert os.path.exists(path)
        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert rows[0]["species"] == "American Robin"


class TestExportJSON:
    def test_export_json(self, exporter, sightings, tmp_path):
        path = str(tmp_path / "test.json")
        result = exporter.export_json(sightings, path)
        assert result == path
        with open(path) as f:
            data = json.load(f)
            assert len(data) == 2
            assert data[0]["species"] == "American Robin"


class TestExportEBird:
    def test_export_ebird(self, exporter, sightings, tmp_path):
        path = str(tmp_path / "ebird.csv")
        result = exporter.export_ebird(sightings, path)
        assert result == path
        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert "Species Name" in rows[0]


class TestExportSummary:
    def test_export_summary(self, exporter, sightings, tmp_path):
        path = str(tmp_path / "summary.json")
        result = exporter.export_summary(sightings, path)
        assert result == path
        with open(path) as f:
            data = json.load(f)
            assert data["total_sightings"] == 2
            assert data["unique_species"] == 2
