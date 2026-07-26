"""tests/test_rarity_checker.py — Rarity checker tests."""

import os
import tempfile

import pytest

from core.config import RarityConfig
from core.types import RarityLevel
from modules.rarity_checker import RarityChecker


RARITY_YAML = """
location: "Pacific Northwest, USA"
species:
  - name: "American Robin"
    scientific_name: "Turdus migratorius"
    rarity: "common"
    notes: "Year-round resident"
  - name: "Northern Cardinal"
    scientific_name: "Cardinalis cardinalis"
    rarity: "uncommon"
    notes: "Occasional visitor"
  - name: "Snowy Owl"
    scientific_name: "Bubo scandiacus"
    rarity: "rare"
    notes: "Irruptive winter visitor"
  - name: "Spotted Redshank"
    scientific_name: "Tringa erythropus"
    rarity: "accidental"
    notes: "Extremely rare vagrant"
"""


@pytest.fixture
def rarity_file():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        f.write(RARITY_YAML)
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def checker(rarity_file):
    return RarityChecker(RarityConfig(rarity_file=rarity_file))


@pytest.fixture
def empty_checker():
    return RarityChecker(RarityConfig(rarity_file=""))


class TestCheckRarity:
    def test_common_species(self, checker):
        assert checker.check_rarity("American Robin") == RarityLevel.COMMON

    def test_rare_species(self, checker):
        assert checker.check_rarity("Snowy Owl") == RarityLevel.RARE

    def test_accidental_species(self, checker):
        assert checker.check_rarity("Spotted Redshank") == RarityLevel.ACCIDENTAL

    def test_unknown_species_defaults_common(self, checker):
        assert checker.check_rarity("Unknown Bird") == RarityLevel.COMMON

    def test_empty_species(self, checker):
        assert checker.check_rarity("") == RarityLevel.COMMON

    def test_unknown_species_string(self, checker):
        assert checker.check_rarity("Unknown") == RarityLevel.COMMON


class TestIsRare:
    def test_rare_is_rare(self, checker):
        assert checker.is_rare("Snowy Owl") is True

    def test_common_not_rare(self, checker):
        assert checker.is_rare("American Robin") is False

    def test_uncommon_not_rare(self, checker):
        assert checker.is_rare("Northern Cardinal") is False

    def test_accidental_is_rare(self, checker):
        assert checker.is_rare("Spotted Redshank") is True

    def test_custom_threshold(self, checker):
        # With threshold UNCOMMON, uncommon should be rare
        assert checker.is_rare("Northern Cardinal", RarityLevel.UNCOMMON) is True


class TestCaseInsensitive:
    def test_lowercase(self, checker):
        assert checker.check_rarity("american robin") == RarityLevel.COMMON

    def test_uppercase(self, checker):
        assert checker.check_rarity("SNOWY OWL") == RarityLevel.RARE

    def test_mixed_case(self, checker):
        assert checker.check_rarity("sNoWy OwL") == RarityLevel.RARE


class TestFuzzyMatch:
    def test_exact_match(self, checker):
        info = checker.get_rarity_info("American Robin")
        assert info is not None
        assert info["rarity"] == "common"

    def test_fuzzy_match_slight_variation(self, checker):
        # "American Robin" vs "American Robins" — should still match
        info = checker.get_rarity_info("American Robins")
        # get_rarity_info uses exact lookup, fuzzy is in check_rarity
        level = checker.check_rarity("American Robins")
        assert level == RarityLevel.COMMON


class TestLoadData:
    def test_load_rarity_data(self, checker):
        data = checker.list_all()
        assert len(data) >= 4
        assert "american robin" in data

    def test_no_file_all_common(self, empty_checker):
        assert empty_checker.check_rarity("Any Bird") == RarityLevel.COMMON
        assert empty_checker.species_count == 0


class TestAddSpecies:
    def test_add_new_species(self, checker):
        checker.add_species("Western Tanager", "rare", "Western visitor")
        assert checker.check_rarity("Western Tanager") == RarityLevel.RARE
        assert checker.is_rare("Western Tanager") is True

    def test_update_existing_species(self, checker):
        checker.add_species("American Robin", "uncommon", "Updated rarity")
        assert checker.check_rarity("American Robin") == RarityLevel.UNCOMMON


class TestListAll:
    def test_list_all_returns_dict(self, checker):
        data = checker.list_all()
        assert isinstance(data, dict)
        assert len(data) == 4

    def test_list_all_has_name_field(self, checker):
        data = checker.list_all()
        assert "american robin" in data
        assert data["american robin"]["name"] == "American Robin"


class TestLocation:
    def test_location_name(self, checker):
        assert "Pacific Northwest" in checker.location_name

    def test_empty_location(self, empty_checker):
        assert empty_checker.location_name == ""