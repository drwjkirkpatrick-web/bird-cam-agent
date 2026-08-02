"""tests/test_identifier.py — Bird identifier tests."""

import os
import tempfile

import pytest

from core.config import Config, HermesBridgeConfig
from core.types import IdentificationResult
from modules.hermes_bridge import HermesBridge
from modules.identifier import BirdIdentifier


@pytest.fixture
def mock_config():
    return Config.create_default_config()


@pytest.fixture
def bridge(mock_config):
    return HermesBridge(mock_config.hermes_bridge)


@pytest.fixture
def identifier(bridge, mock_config):
    return BirdIdentifier(bridge, mock_config)


@pytest.fixture
def temp_photo():
    with tempfile.NamedTemporaryFile(
        suffix=".jpg", delete=False, mode="wb"
    ) as f:
        f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9")
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestIdentify:
    def test_identify_returns_result(self, identifier, temp_photo):
        result = identifier.identify(temp_photo)
        assert isinstance(result, IdentificationResult)
        assert result.is_bird is True
        assert result.species != "Unknown"

    def test_identify_missing_photo(self, identifier):
        result = identifier.identify("/nonexistent/photo.jpg")
        assert result.is_bird is False

    def test_identify_batch(self, identifier, temp_photo):
        results = identifier.identify_batch([temp_photo, temp_photo, temp_photo])
        assert len(results) == 3
        for r in results:
            assert isinstance(r, IdentificationResult)

    def test_identify_batch_empty(self, identifier):
        results = identifier.identify_batch([])
        assert results == []


class TestRetry:
    def test_retry_succeeds_eventually(self, identifier, temp_photo):
        # Mock bridge always succeeds, so just verify it works
        result = identifier.identify_with_retry(temp_photo, max_retries=3)
        assert isinstance(result, IdentificationResult)

    def test_retry_returns_result(self, identifier, temp_photo):
        result = identifier.identify_with_retry(temp_photo, max_retries=1)
        assert isinstance(result, IdentificationResult)


class TestHistory:
    def test_history_tracks_results(self, identifier, temp_photo):
        identifier.identify(temp_photo)
        identifier.identify(temp_photo)
        history = identifier.get_identification_history()
        assert len(history) == 2

    def test_history_most_recent_first(self, identifier, temp_photo):
        r1 = identifier.identify(temp_photo)
        r2 = identifier.identify(temp_photo)
        history = identifier.get_identification_history()
        assert history[0] == r2
        assert history[1] == r1

    def test_clear_history(self, identifier, temp_photo):
        identifier.identify(temp_photo)
        identifier.clear_history()
        assert identifier.get_identification_history() == []


class TestConfidence:
    def test_check_confidence_above_threshold(self, identifier):
        result = IdentificationResult(species="Robin", confidence=0.9)
        assert identifier.check_confidence(result) is True

    def test_check_confidence_below_threshold(self, identifier):
        result = IdentificationResult(species="Robin", confidence=0.3)
        assert identifier.check_confidence(result) is False


class TestTwoTierLocalClassifier:
    """Test the two-tier identification: local classifier first, Hermes fallback."""

    def test_local_classifier_high_confidence_skips_hermes(self, bridge, mock_config, temp_photo):
        """When local classifier is confident, Hermes bridge is never called."""
        local = _FakeLocalClassifier(
            result=IdentificationResult(
                species="American Robin",
                confidence=0.95,
                is_bird=True,
                description="Local hit",
            )
        )
        identifier = BirdIdentifier(bridge, mock_config, local_classifier=local)
        result = identifier.identify(temp_photo)

        assert result.species == "American Robin"
        assert result.confidence == 0.95
        assert local.call_count == 1
        assert bridge._mock_index == 0  # Hermes bridge never called

    def test_local_classifier_low_confidence_falls_back(self, bridge, mock_config, temp_photo):
        """When local classifier is low-confidence, Hermes bridge is used."""
        local = _FakeLocalClassifier(
            result=IdentificationResult(
                species="Unknown",
                confidence=0.3,
                is_bird=False,
                description="Local miss",
            )
        )
        identifier = BirdIdentifier(bridge, mock_config, local_classifier=local)
        result = identifier.identify(temp_photo)

        # Falls back to Hermes bridge
        assert result.is_bird is True
        assert result.species != "Unknown"
        assert local.call_count == 1

    def test_local_classifier_not_ready_uses_hermes(self, bridge, mock_config, temp_photo):
        """When local classifier is not ready, Hermes bridge is used directly."""
        local = _FakeLocalClassifier(ready=False)
        identifier = BirdIdentifier(bridge, mock_config, local_classifier=local)
        result = identifier.identify(temp_photo)

        assert result.is_bird is True
        assert result.species != "Unknown"
        assert local.call_count == 0  # Never called because not ready

    def test_no_local_classifier_uses_hermes(self, bridge, mock_config, temp_photo):
        """When no local classifier is provided, Hermes bridge is used directly."""
        identifier = BirdIdentifier(bridge, mock_config, local_classifier=None)
        result = identifier.identify(temp_photo)

        assert result.is_bird is True
        assert result.species != "Unknown"

    def test_local_classifier_returns_not_bird_falls_back(self, bridge, mock_config, temp_photo):
        """When local classifier says 'not a bird' (low confidence), fall back."""
        local = _FakeLocalClassifier(
            result=IdentificationResult(
                species="Unknown",
                confidence=0.0,
                is_bird=False,
                description="No bird detected",
            )
        )
        identifier = BirdIdentifier(bridge, mock_config, local_classifier=local)
        result = identifier.identify(temp_photo)

        # Falls back to Hermes
        assert result.is_bird is True
        assert result.species != "Unknown"


class _FakeLocalClassifier:
    """Fake LocalBirdClassifier for testing two-tier behavior."""

    def __init__(self, result=None, ready=True):
        self._result = result
        self._ready = ready
        self.call_count = 0

    def is_ready(self):
        return self._ready

    def get_supported_species(self):
        return ["Mock Sparrow"] if self._ready else []

    def identify(self, photo_path):
        self.call_count += 1
        if self._result is None:
            return IdentificationResult(species="Unknown", is_bird=False)
        return IdentificationResult(
            species=self._result.species,
            confidence=self._result.confidence,
            is_bird=self._result.is_bird,
            description=self._result.description,
        )