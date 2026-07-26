"""tests/test_hermes_bridge.py — Hermes bridge tests."""

import json
import os
import tempfile

import pytest

from core.config import HermesBridgeConfig
from core.types import IdentificationResult
from modules.hermes_bridge import HermesBridge


@pytest.fixture
def mock_config():
    return HermesBridgeConfig(mode="mock", mock_mode=True)


@pytest.fixture
def bridge(mock_config):
    return HermesBridge(mock_config)


@pytest.fixture
def temp_photo():
    """Create a temporary JPEG file for testing."""
    with tempfile.NamedTemporaryFile(
        suffix=".jpg", delete=False, mode="wb"
    ) as f:
        # Minimal JPEG header + data
        f.write(
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01"
            b"\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06"
            b"\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b"
            b"\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c"
            b"\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<34.2\xff\xc0"
            b"\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc9"
            b"\x00\x14\x11\x01\x00\x01\x00\x01\x01\x11\x00\xff\xda"
            b"\x00\x08\x01\x01\x00\x00?\x00\xd2\xcf \xff\xd9"
        )
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestMockMode:
    def test_mock_identify_returns_result(self, bridge, temp_photo):
        result = bridge.identify_bird(temp_photo)
        assert isinstance(result, IdentificationResult)
        assert result.is_bird is True
        assert result.species != "Unknown"
        assert result.confidence > 0

    def test_mock_identify_cycles_results(self, bridge, temp_photo):
        results = [bridge.identify_bird(temp_photo) for _ in range(4)]
        # Should cycle through mock results
        species = [r.species for r in results]
        assert len(set(species)) > 1  # at least 2 different species

    def test_missing_photo_returns_unknown(self, bridge):
        result = bridge.identify_bird("/nonexistent/path.jpg")
        assert result.is_bird is False
        assert result.species == "Unknown"


class TestPromptAndParsing:
    def test_build_prompt_contains_bird_instructions(self, bridge):
        prompt = bridge._build_prompt()
        assert "bird" in prompt.lower()
        assert "json" in prompt.lower()
        assert "species" in prompt.lower()
        assert "scientific_name" in prompt.lower()
        assert "is_bird" in prompt.lower()
        assert "confidence" in prompt.lower()

    def test_parse_valid_json(self, bridge):
        raw = json.dumps({
            "species": "Blue Jay",
            "scientific_name": "Cyanocitta cristata",
            "confidence": 0.95,
            "is_bird": True,
            "attributes": {"color": "blue", "size": "medium"},
            "description": "A blue and white songbird",
            "alternative_species": ["Steller's Jay"],
        })
        result = bridge._parse_response(raw)
        assert result.species == "Blue Jay"
        assert result.scientific_name == "Cyanocitta cristata"
        assert result.confidence == 0.95
        assert result.is_bird is True
        assert result.attributes["color"] == "blue"
        assert "Steller's Jay" in result.alternative_species

    def test_parse_malformed_json(self, bridge):
        raw = "This is not JSON at all"
        result = bridge._parse_response(raw)
        assert result.is_bird is False
        assert result.species == "Unknown"

    def test_parse_json_in_code_fence(self, bridge):
        raw = '```json\n{"species": "Crow", "is_bird": true, "confidence": 0.8}\n```'
        result = bridge._parse_response(raw)
        assert result.species == "Crow"
        assert result.is_bird is True

    def test_parse_non_bird_detection(self, bridge):
        raw = json.dumps({
            "species": "Unknown",
            "is_bird": False,
            "confidence": 0.0,
            "description": "No bird visible in image",
        })
        result = bridge._parse_response(raw)
        assert result.is_bird is False
        assert result.species == "Unknown"

    def test_parse_confidence_clamped(self, bridge):
        raw = json.dumps({"species": "Eagle", "confidence": 1.5, "is_bird": True})
        result = bridge._parse_response(raw)
        assert result.confidence == 1.0

        raw2 = json.dumps({"species": "Eagle", "confidence": -0.5, "is_bird": True})
        result2 = bridge._parse_response(raw2)
        assert result2.confidence == 0.0

    def test_parse_missing_fields_use_defaults(self, bridge):
        raw = json.dumps({"species": "Sparrow"})
        result = bridge._parse_response(raw)
        assert result.species == "Sparrow"
        assert result.confidence == 0.0
        assert result.is_bird is False  # defaults to False
        assert result.attributes == {}

    def test_extract_json_direct(self, bridge):
        assert bridge._extract_json('{"key": "value"}') == '{"key": "value"}'

    def test_extract_json_none(self, bridge):
        assert bridge._extract_json("no json here") is None


class TestHealthCheck:
    def test_mock_health_check(self, bridge):
        result = bridge.health_check()
        assert result["healthy"] is True
        assert result["mode"] == "mock"