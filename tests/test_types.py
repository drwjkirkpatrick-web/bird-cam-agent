"""tests/test_types.py — Core type tests."""

from core.types import (
    RarityLevel,
    IdentificationResult,
    BirdSighting,
    CameraConfig,
    SightingRecord,
)


class TestRarityLevel:
    def test_from_string_common(self):
        assert RarityLevel.from_string("common") == RarityLevel.COMMON

    def test_from_string_rare(self):
        assert RarityLevel.from_string("rare") == RarityLevel.RARE

    def test_from_string_case_insensitive(self):
        assert RarityLevel.from_string("RARE") == RarityLevel.RARE
        assert RarityLevel.from_string("Very Rare") == RarityLevel.VERY_RARE

    def test_from_string_unknown_defaults_common(self):
        assert RarityLevel.from_string("nonexistent") == RarityLevel.COMMON

    def test_from_string_empty(self):
        assert RarityLevel.from_string("") == RarityLevel.COMMON
        assert RarityLevel.from_string(None) == RarityLevel.COMMON

    def test_comparison(self):
        assert RarityLevel.RARE > RarityLevel.COMMON
        assert RarityLevel.COMMON < RarityLevel.RARE
        assert RarityLevel.VERY_RARE >= RarityLevel.RARE
        assert RarityLevel.COMMON <= RarityLevel.COMMON


class TestIdentificationResult:
    def test_round_trip(self):
        result = IdentificationResult(
            species="American Robin",
            scientific_name="Turdus migratorius",
            confidence=0.92,
            is_bird=True,
            attributes={"color": "brown"},
            description="A robin",
            alternative_species=["European Robin"],
        )
        d = result.to_dict()
        restored = IdentificationResult.from_dict(d)
        assert restored.species == result.species
        assert restored.scientific_name == result.scientific_name
        assert restored.confidence == result.confidence
        assert restored.is_bird == result.is_bird
        assert restored.attributes == result.attributes
        assert restored.description == result.description
        assert restored.alternative_species == result.alternative_species

    def test_defaults(self):
        result = IdentificationResult()
        assert result.species == "Unknown"
        assert result.confidence == 0.0
        assert result.is_bird is True
        assert result.attributes == {}
        assert result.alternative_species == []

    def test_from_dict_filters_unknown_keys(self):
        data = {"species": "Crow", "bogus_field": "should be ignored"}
        result = IdentificationResult.from_dict(data)
        assert result.species == "Crow"


class TestBirdSighting:
    def test_round_trip(self):
        sighting = BirdSighting(
            species="Northern Cardinal",
            scientific_name="Cardinalis cardinalis",
            confidence=0.88,
            photo_path="/data/photos/bird_001.jpg",
            rarity_level=RarityLevel.UNCOMMON,
            notes="Male, bright red",
            location="Backyard feeder",
            alternative_species=["Scarlet Tanager"],
        )
        d = sighting.to_dict()
        # RarityLevel should be serialized as string
        assert d["rarity_level"] == "uncommon"
        restored = BirdSighting.from_dict(d)
        assert restored.species == sighting.species
        assert restored.rarity_level == RarityLevel.UNCOMMON
        assert restored.alternative_species == sighting.alternative_species

    def test_auto_id(self):
        s1 = BirdSighting()
        s2 = BirdSighting()
        assert s1.sighting_id != s2.sighting_id
        assert len(s1.sighting_id) > 0

    def test_is_rare_property(self):
        rare = BirdSighting(rarity_level=RarityLevel.RARE)
        common = BirdSighting(rarity_level=RarityLevel.COMMON)
        assert rare.is_rare is True
        assert common.is_rare is False

    def test_from_dict_string_rarity(self):
        data = {"species": "Owl", "rarity_level": "very_rare"}
        sighting = BirdSighting.from_dict(data)
        assert sighting.rarity_level == RarityLevel.VERY_RARE


class TestCameraConfig:
    def test_defaults(self):
        config = CameraConfig()
        assert config.mock_mode is True
        assert config.resolution_width == 1280
        assert config.capture_interval == 30.0

    def test_round_trip(self):
        config = CameraConfig(device_index=1, resolution_width=1920)
        d = config.to_dict()
        restored = CameraConfig.from_dict(d)
        assert restored.device_index == 1
        assert restored.resolution_width == 1920


class TestSightingRecord:
    def test_round_trip(self):
        record = SightingRecord(
            sighting_id="abc-123",
            file_size=102400,
            file_hash="abc123def456",
        )
        d = record.to_dict()
        restored = SightingRecord.from_dict(d)
        assert restored.sighting_id == record.sighting_id
        assert restored.file_size == record.file_size
        assert restored.file_hash == record.file_hash