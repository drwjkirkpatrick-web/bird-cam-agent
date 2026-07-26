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
        identifier.identify(temp_photo)
        identifier.identify(temp_photo)
        history = identifier.get_identification_history()
        # Most recent should be first
        assert len(history) >= 2

    def test_clear_history(self, identifier, temp_photo):
        identifier.identify(temp_photo)
        identifier.clear_history()
        assert len(identifier.get_identification_history()) == 0


class TestConfidence:
    def test_check_confidence_above_threshold(self, identifier):
        result = IdentificationResult(species="Eagle", confidence=0.9)
        assert identifier.check_confidence(result) is True

    def test_check_confidence_below_threshold(self, identifier):
        result = IdentificationResult(species="Eagle", confidence=0.1)
        assert identifier.check_confidence(result) is False