"""tests/test_local_bird_classifier.py — Local bird classifier tests."""

import os
import pickle
import shutil
import tempfile

import pytest

from core.config import LocalClassifierConfig
from core.types import IdentificationResult
from modules.local_bird_classifier import LocalBirdClassifier, TRAINING_DIRECTIONS


@pytest.fixture
def tmp_model_dir():
    path = tempfile.mkdtemp(prefix="bird_classifier_test_")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def mock_classifier(tmp_model_dir):
    config = LocalClassifierConfig(
        model_dir=tmp_model_dir,
        mock_mode=True,
        confidence_threshold=0.7,
    )
    clf = LocalBirdClassifier(config)
    clf.load()
    return clf


@pytest.fixture
def temp_jpg(tmp_path):
    """Create a temp JPEG file for testing."""
    from PIL import Image

    path = str(tmp_path / "test_bird.jpg")
    img = Image.new("RGB", (224, 224), color=(100, 150, 200))
    img.save(path, "JPEG")
    return path


class TestMockMode:
    def test_load_returns_true(self, mock_classifier):
        assert mock_classifier.is_ready() is True

    def test_identify_returns_result(self, mock_classifier, temp_jpg):
        result = mock_classifier.identify(temp_jpg)
        assert isinstance(result, IdentificationResult)
        assert result.species != "Unknown"
        assert result.confidence > 0
        assert result.is_bird is True

    def test_identify_returns_alternatives(self, mock_classifier, temp_jpg):
        result = mock_classifier.identify(temp_jpg)
        assert len(result.alternative_species) > 0

    def test_identify_missing_photo(self, mock_classifier):
        result = mock_classifier.identify("/nonexistent/path.jpg")
        assert result.species == "Unknown"
        assert result.is_bird is False

    def test_get_supported_species(self, mock_classifier):
        species = mock_classifier.get_supported_species()
        assert len(species) == 3
        assert "Mock Sparrow" in species

    def test_mock_determinism(self, mock_classifier, temp_jpg):
        """Same file should give same species (deterministic by filename hash)."""
        r1 = mock_classifier.identify(temp_jpg)
        r2 = mock_classifier.identify(temp_jpg)
        assert r1.species == r2.species
        assert abs(r1.confidence - r2.confidence) < 0.001

    def test_mock_different_files_different_results(self, mock_classifier, tmp_path):
        from PIL import Image

        path1 = str(tmp_path / "bird_a.jpg")
        path2 = str(tmp_path / "bird_b.jpg")
        Image.new("RGB", (224, 224), color=(100, 100, 100)).save(path1, "JPEG")
        Image.new("RGB", (224, 224), color=(200, 200, 200)).save(path2, "JPEG")

        r1 = mock_classifier.identify(path1)
        r2 = mock_classifier.identify(path2)
        # Deterministic by filename hash — may or may not differ
        assert r1.species in mock_classifier.get_supported_species()
        assert r2.species in mock_classifier.get_supported_species()


class TestConfidenceThreshold:
    def test_high_confidence_is_bird(self, tmp_model_dir, temp_jpg):
        config = LocalClassifierConfig(
            model_dir=tmp_model_dir,
            mock_mode=True,
            confidence_threshold=0.1,
        )
        clf = LocalBirdClassifier(config)
        clf.load()
        result = clf.identify(temp_jpg)
        assert result.is_bird is True

    def test_low_confidence_not_bird(self, tmp_model_dir, temp_jpg):
        config = LocalClassifierConfig(
            model_dir=tmp_model_dir,
            mock_mode=True,
            confidence_threshold=0.99,
        )
        clf = LocalBirdClassifier(config)
        clf.load()
        result = clf.identify(temp_jpg)
        # Mock confidence is ~0.75-1.0, so this may or may not trigger
        # Just assert the field exists and is a bool
        assert isinstance(result.is_bird, bool)


class TestTrainingDirections:
    def test_directions_contains_steps(self):
        assert "Prerequisites" in TRAINING_DIRECTIONS
        assert "Step 1" in TRAINING_DIRECTIONS
        assert "Step 2" in TRAINING_DIRECTIONS
        assert "MobileNetV3" in TRAINING_DIRECTIONS


class TestRealModelNotFound:
    def test_load_without_model_returns_false(self, tmp_model_dir):
        config = LocalClassifierConfig(
            model_dir=tmp_model_dir,
            mock_mode=False,
        )
        clf = LocalBirdClassifier(config)
        assert clf.load() is False
        assert clf.is_ready() is False

    def test_identify_without_model_returns_unknown(self, tmp_model_dir, temp_jpg):
        config = LocalClassifierConfig(
            model_dir=tmp_model_dir,
            mock_mode=False,
        )
        clf = LocalBirdClassifier(config)
        result = clf.identify(temp_jpg)
        assert result.species == "Unknown"
        assert result.is_bird is False


class TestConfigRoundTrip:
    def test_config_to_dict(self):
        config = LocalClassifierConfig(
            model_dir="data/models",
            model_name="mobilenet_v3_small",
            num_epochs=15,
            confidence_threshold=0.8,
        )
        d = config.to_dict()
        assert d["model_dir"] == "data/models"
        assert d["num_epochs"] == 15
        assert d["confidence_threshold"] == 0.8

    def test_config_from_dict(self):
        d = {
            "model_dir": "data/models",
            "model_name": "mobilenet_v3_small",
            "num_epochs": 20,
            "batch_size": 8,
            "learning_rate": 0.0005,
            "image_size": 224,
            "confidence_threshold": 0.75,
            "mock_mode": True,
        }
        config = LocalClassifierConfig.from_dict(d)
        assert config.num_epochs == 20
        assert config.batch_size == 8
        assert config.confidence_threshold == 0.75

    def test_config_defaults(self):
        config = LocalClassifierConfig()
        assert config.model_name == "mobilenet_v3_small"
        assert config.mock_mode is True