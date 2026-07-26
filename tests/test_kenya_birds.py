"""tests/test_kenya_birds.py — Kenya bird database tests."""

import os
import tempfile

import pytest

from modules.kenya_birds import (
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
        assert "Nairobi" in LOCATION_NAME
        assert "Kenya" in LOCATION_NAME

    def test_all_entries_have_required_fields(self):
        for s in SPECIES_DATA:
            assert "name" in s
            assert "scientific_name" in s
            assert "rarity" in s
            assert "notes" in s

    def test_rarity_values_valid(self):
        valid = {"common", "uncommon", "rare", "very_rare", "accidental"}
        for s in SPECIES_DATA:
            assert s["rarity"] in valid


class TestGetRarityDict:
    def test_returns_dict(self):
        d = get_rarity_dict()
        assert isinstance(d, dict)
        assert len(d) == len(SPECIES_DATA)

    def test_keys_are_lowercase(self):
        d = get_rarity_dict()
        for key in d:
            assert key == key.lower()

    def test_contains_lilac_breasted_roller(self):
        d = get_rarity_dict()
        assert "lilac-breasted roller" in d
        assert d["lilac-breasted roller"]["rarity"] == "common"


class TestRarityYAML:
    def test_generates_yaml(self):
        yaml_str = get_rarity_yaml()
        assert "location:" in yaml_str
        assert "Nairobi" in yaml_str
        assert "Lilac-breasted Roller" in yaml_str

    def test_write_rarity_file(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            path = f.name
        try:
            write_rarity_file(path)
            assert os.path.exists(path)
            content = open(path).read()
            assert "Nairobi" in content
        finally:
            os.unlink(path)


class TestFilters:
    def test_by_habitat_savanna(self):
        savanna = get_species_by_habitat("savanna")
        assert len(savanna) > 0

    def test_by_habitat_wetland(self):
        wetland = get_species_by_habitat("wetland")
        assert len(wetland) > 0

    def test_by_rarity_rare(self):
        rare = get_species_by_rarity("rare")
        assert len(rare) > 0

    def test_by_rarity_accidental(self):
        accidental = get_species_by_rarity("accidental")
        assert len(accidental) >= 1


class TestStats:
    def test_stats_structure(self):
        stats = get_stats()
        assert "total_species" in stats
        assert "location" in stats
        assert "rarity_breakdown" in stats

    def test_total_matches(self):
        stats = get_stats()
        assert stats["total_species"] == len(SPECIES_DATA)

    def test_has_common_species(self):
        stats = get_stats()
        assert stats["rarity_breakdown"].get("common", 0) > 0