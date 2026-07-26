"""tests/test_pnw_birds.py — Pacific Northwest bird database tests."""

import os
import tempfile

import pytest

from modules.pnw_birds import (
    LOCATION_NAME,
    SPECIES_DATA,
    get_species_list,
    get_rarity_dict,
    get_rarity_yaml,
    write_rarity_file,
    get_species_by_habitat,
    get_species_by_season,
    get_species_by_rarity,
    get_stats,
)


class TestSpeciesData:
    def test_has_species(self):
        assert len(SPECIES_DATA) > 30

    def test_location_name(self):
        assert "McIver" in LOCATION_NAME
        assert "Oregon" in LOCATION_NAME

    def test_all_entries_have_required_fields(self):
        for s in SPECIES_DATA:
            assert "name" in s
            assert "scientific_name" in s
            assert "rarity" in s
            assert "notes" in s

    def test_rarity_values_valid(self):
        valid = {"common", "uncommon", "rare", "very_rare", "accidental"}
        for s in SPECIES_DATA:
            assert s["rarity"] in valid, f"Invalid rarity: {s['rarity']} for {s['name']}"


class TestGetRarityDict:
    def test_returns_dict(self):
        d = get_rarity_dict()
        assert isinstance(d, dict)
        assert len(d) == len(SPECIES_DATA)

    def test_keys_are_lowercase(self):
        d = get_rarity_dict()
        for key in d:
            assert key == key.lower()

    def test_contains_american_robin(self):
        d = get_rarity_dict()
        assert "american robin" in d
        assert d["american robin"]["rarity"] == "common"


class TestRarityYAML:
    def test_generates_yaml(self):
        yaml_str = get_rarity_yaml()
        assert "location:" in yaml_str
        assert "McIver" in yaml_str
        assert "American Robin" in yaml_str

    def test_write_rarity_file(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            path = f.name
        try:
            write_rarity_file(path)
            assert os.path.exists(path)
            content = open(path).read()
            assert "McIver" in content
        finally:
            os.unlink(path)


class TestFilters:
    def test_by_habitat(self):
        riparian = get_species_by_habitat("riparian")
        assert len(riparian) > 0
        for s in riparian:
            assert s["habitat"] == "riparian"

    def test_by_season(self):
        summer = get_species_by_season("summer")
        assert len(summer) > 0

    def test_by_rarity(self):
        rare = get_species_by_rarity("rare")
        assert len(rare) > 0
        for s in rare:
            assert s["rarity"] == "rare"

    def test_by_rarity_accidental(self):
        accidental = get_species_by_rarity("accidental")
        assert len(accidental) >= 1


class TestStats:
    def test_stats_structure(self):
        stats = get_stats()
        assert "total_species" in stats
        assert "location" in stats
        assert "rarity_breakdown" in stats
        assert "habitat_breakdown" in stats
        assert "season_breakdown" in stats

    def test_total_matches(self):
        stats = get_stats()
        assert stats["total_species"] == len(SPECIES_DATA)

    def test_has_common_species(self):
        stats = get_stats()
        assert stats["rarity_breakdown"].get("common", 0) > 0

    def test_has_rare_species(self):
        stats = get_stats()
        assert stats["rarity_breakdown"].get("rare", 0) > 0