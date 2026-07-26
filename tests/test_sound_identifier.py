"""tests/test_sound_identifier.py — Sound identifier tests."""

import json
import os
import tempfile

import pytest

from modules.sound_identifier import SoundIdentifier


@pytest.fixture
def identifier():
    """Default mock-mode identifier."""
    return SoundIdentifier()


@pytest.fixture
def identifier_with_config():
    """Identifier built from an explicit config dict."""
    return SoundIdentifier(
        config={
            "hermes_api_url": "http://localhost:9999",
            "mock_mode": True,
            "confidence_threshold": 0.7,
        }
    )


@pytest.fixture
def temp_audio():
    """Create a temporary WAV file for testing."""
    with tempfile.NamedTemporaryFile(
        suffix=".wav", delete=False, mode="wb"
    ) as f:
        # Minimal WAV header (RIFF chunk)
        f.write(
            b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
            b"\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00"
            b"\x02\x00\x10\x00data\x00\x00\x00\x00"
        )
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestMockMode:
    def test_mock_identify_returns_valid_dict(self, identifier, temp_audio):
        """Mock returns valid dict — primary required test."""
        result = identifier.identify_sound(temp_audio)
        assert isinstance(result, dict)
        assert "species" in result
        assert "scientific_name" in result
        assert "confidence" in result
        assert "is_bird" in result
        assert "description" in result
        assert "alternative_species" in result
        assert result["is_bird"] is True
        assert result["species"] != "Unknown"
        assert result["confidence"] > 0

    def test_mock_identify_cycles_species(self, identifier, temp_audio):
        """Mock should cycle through 3 species."""
        results = [identifier.identify_sound(temp_audio) for _ in range(4)]
        species = [r["species"] for r in results]
        assert len(set(species)) >= 2  # at least 2 different species

    def test_mock_identify_returns_copy(self, identifier, temp_audio):
        """Each mock result should be an independent copy."""
        r1 = identifier.mock_identify(temp_audio)
        r1["species"] = "MUTATED"
        r2 = identifier.mock_identify(temp_audio)
        assert r2["species"] != "MUTATED"

    def test_missing_audio_returns_unknown(self, identifier):
        result = identifier.identify_sound("/nonexistent/audio.wav")
        assert result["is_bird"] is False
        assert result["species"] == "Unknown"
        assert result["confidence"] == 0.0


class TestBatchProcessing:
    def test_batch_returns_list_of_dicts(self, identifier, temp_audio):
        results = identifier.identify_batch(
            [temp_audio, temp_audio, temp_audio]
        )
        assert isinstance(results, list)
        assert len(results) == 3
        for r in results:
            assert isinstance(r, dict)
            assert "species" in r

    def test_batch_empty_returns_empty_list(self, identifier):
        results = identifier.identify_batch([])
        assert results == []


class TestRetry:
    def test_retry_succeeds_eventually(self, identifier, temp_audio):
        """Retry on failure — mock always succeeds so verify it works."""
        result = identifier.identify_with_retry(temp_audio, max_retries=3)
        assert isinstance(result, dict)
        assert result["is_bird"] is True

    def test_retry_with_one_attempt(self, identifier, temp_audio):
        result = identifier.identify_with_retry(temp_audio, max_retries=1)
        assert isinstance(result, dict)
        assert result["species"] != "Unknown"

    def test_retry_on_missing_file_returns_unknown(self, identifier):
        """Missing file should return unknown after retries."""
        result = identifier.identify_with_retry(
            "/nonexistent/audio.wav", max_retries=3
        )
        assert result["is_bird"] is False
        assert result["species"] == "Unknown"


class TestPromptAndParsing:
    def test_build_prompt_contains_bird_sound_instructions(self, identifier):
        """_build_prompt contains bird sound instructions."""
        prompt = identifier._build_prompt()
        assert "bird" in prompt.lower()
        assert "sound" in prompt.lower() or "audio" in prompt.lower()
        assert "json" in prompt.lower()
        assert "species" in prompt.lower()
        assert "scientific_name" in prompt.lower()
        assert "is_bird" in prompt.lower()
        assert "confidence" in prompt.lower()
        assert "alternative_species" in prompt.lower()
        assert "description" in prompt.lower()

    def test_parse_response_extracts_json(self, identifier):
        """_parse_response extracts JSON from a clean JSON string."""
        raw = json.dumps(
            {
                "species": "Blue Jay",
                "scientific_name": "Cyanocitta cristata",
                "confidence": 0.95,
                "is_bird": True,
                "description": "A loud, jay-like call.",
                "alternative_species": ["Steller's Jay"],
            }
        )
        result = identifier._parse_response(raw)
        assert result["species"] == "Blue Jay"
        assert result["scientific_name"] == "Cyanocitta cristata"
        assert result["confidence"] == 0.95
        assert result["is_bird"] is True
        assert "Steller's Jay" in result["alternative_species"]

    def test_parse_response_extracts_json_from_code_fence(self, identifier):
        """_parse_response extracts JSON wrapped in markdown fences."""
        raw = (
            '```json\n{"species": "Crow", "is_bird": true, '
            '"confidence": 0.8}\n```'
        )
        result = identifier._parse_response(raw)
        assert result["species"] == "Crow"
        assert result["is_bird"] is True
        assert result["confidence"] == 0.8

    def test_parse_response_handles_malformed_json(self, identifier):
        """_parse_response handles malformed JSON gracefully."""
        raw = "This is not JSON at all"
        result = identifier._parse_response(raw)
        assert result["is_bird"] is False
        assert result["species"] == "Unknown"
        assert result["confidence"] == 0.0

    def test_parse_response_handles_missing_fields(self, identifier):
        """Missing fields should use safe defaults."""
        raw = json.dumps({"species": "Sparrow"})
        result = identifier._parse_response(raw)
        assert result["species"] == "Sparrow"
        assert result["confidence"] == 0.0
        assert result["is_bird"] is False  # defaults to False
        assert result["alternative_species"] == []

    def test_parse_response_clamps_confidence(self, identifier):
        """Confidence above 1.0 should be clamped to 1.0."""
        raw = json.dumps(
            {"species": "Eagle", "confidence": 1.5, "is_bird": True}
        )
        result = identifier._parse_response(raw)
        assert result["confidence"] == 1.0

    def test_parse_response_non_bird_sound(self, identifier):
        """Non-bird sound returns is_bird=False."""
        raw = json.dumps(
            {
                "species": "Unknown",
                "is_bird": False,
                "confidence": 0.0,
                "description": "No bird sound detected — appears to be wind noise",
            }
        )
        result = identifier._parse_response(raw)
        assert result["is_bird"] is False
        assert result["species"] == "Unknown"

    def test_extract_json_direct(self, identifier):
        assert identifier._extract_json('{"key": "value"}') == '{"key": "value"}'

    def test_extract_json_none(self, identifier):
        assert identifier._extract_json("no json here") is None


class TestHistory:
    def test_history_tracks_results(self, identifier, temp_audio):
        identifier.identify_sound(temp_audio)
        identifier.identify_sound(temp_audio)
        history = identifier.get_history()
        assert len(history) == 2
        for h in history:
            assert isinstance(h, dict)
            assert "species" in h

    def test_history_most_recent_first(self, identifier, temp_audio):
        identifier.identify_sound(temp_audio)
        identifier.identify_sound(temp_audio)
        history = identifier.get_history()
        # Most recent should be first
        assert len(history) >= 2

    def test_history_after_missing_file(self, identifier):
        """Even failed identifications should be tracked."""
        identifier.identify_sound("/nonexistent/audio.wav")
        history = identifier.get_history()
        assert len(history) == 1
        assert history[0]["species"] == "Unknown"


class TestHealthCheck:
    def test_health_check_mock_mode(self, identifier):
        """health_check in mock mode returns healthy."""
        result = identifier.health_check()
        assert result["healthy"] is True
        assert result["mode"] == "mock"

    def test_health_check_with_config(self, identifier_with_config):
        result = identifier_with_config.health_check()
        assert result["healthy"] is True
        assert result["mode"] == "mock"


class TestConfidenceThreshold:
    def test_confidence_threshold_default(self, identifier):
        """Default confidence threshold is 0.5."""
        assert identifier.confidence_threshold == 0.5

    def test_confidence_threshold_custom(self, identifier_with_config):
        """Custom threshold is respected."""
        assert identifier_with_config.confidence_threshold == 0.7

    def test_mock_confidence_above_default_threshold(self, identifier, temp_audio):
        """Mock results should have confidence above the default threshold."""
        result = identifier.identify_sound(temp_audio)
        assert result["confidence"] >= identifier.confidence_threshold


class TestConfig:
    def test_config_defaults(self):
        """No config uses sensible defaults."""
        si = SoundIdentifier()
        assert si.mock_mode is True
        assert si.confidence_threshold == 0.5
        assert si.hermes_api_url == "http://127.0.0.1:9119"

    def test_config_explicit(self, identifier_with_config):
        assert identifier_with_config.mock_mode is True
        assert identifier_with_config.hermes_api_url == "http://localhost:9999"