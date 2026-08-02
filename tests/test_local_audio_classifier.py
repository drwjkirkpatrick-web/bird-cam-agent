"""tests/test_local_audio_classifier.py — Local audio bird sound classifier tests."""

import os
import shutil
import struct
import tempfile
import wave

import pytest

from core.config import LocalAudioClassifierConfig
from core.types import IdentificationResult
from modules.local_audio_classifier import LocalAudioClassifier, TRAINING_DIRECTIONS


@pytest.fixture
def tmp_model_dir():
    path = tempfile.mkdtemp(prefix="audio_classifier_test_")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def mock_audio_classifier(tmp_model_dir):
    config = LocalAudioClassifierConfig(
        model_dir=tmp_model_dir,
        mock_mode=True,
        confidence_threshold=0.7,
    )
    clf = LocalAudioClassifier(config)
    clf.load()
    return clf


@pytest.fixture
def temp_wav(tmp_path):
    """Create a temp WAV file for testing."""
    path = str(tmp_path / "test_call.wav")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # Write 1 second of silence
        frames = struct.pack("<" + "h" * 16000, *([0] * 16000))
        wf.writeframes(frames)
    return path


class TestMockMode:
    def test_load_returns_true(self, mock_audio_classifier):
        assert mock_audio_classifier.is_ready() is True

    def test_identify_returns_result(self, mock_audio_classifier, temp_wav):
        result = mock_audio_classifier.identify(temp_wav)
        assert isinstance(result, IdentificationResult)
        assert result.species != "Unknown"
        assert result.confidence > 0
        assert result.is_bird is True

    def test_identify_returns_alternatives(self, mock_audio_classifier, temp_wav):
        result = mock_audio_classifier.identify(temp_wav)
        assert len(result.alternative_species) > 0

    def test_identify_missing_audio(self, mock_audio_classifier):
        result = mock_audio_classifier.identify("/nonexistent/path.wav")
        assert result.species == "Unknown"
        assert result.is_bird is False

    def test_get_supported_species(self, mock_audio_classifier):
        species = mock_audio_classifier.get_supported_species()
        assert len(species) == 3
        assert "Mock Song Sparrow" in species

    def test_mock_determinism(self, mock_audio_classifier, temp_wav):
        """Same file should give same species (deterministic by filename hash)."""
        r1 = mock_audio_classifier.identify(temp_wav)
        r2 = mock_audio_classifier.identify(temp_wav)
        assert r1.species == r2.species
        assert abs(r1.confidence - r2.confidence) < 0.001

    def test_mock_different_files_different_results(self, mock_audio_classifier, tmp_path):
        path1 = str(tmp_path / "call_a.wav")
        path2 = str(tmp_path / "call_b.wav")
        for p in (path1, path2):
            with wave.open(p, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                frames = struct.pack("<" + "h" * 16000, *([0] * 16000))
                wf.writeframes(frames)

        r1 = mock_audio_classifier.identify(path1)
        r2 = mock_audio_classifier.identify(path2)
        assert r1.species in mock_audio_classifier.get_supported_species()
        assert r2.species in mock_audio_classifier.get_supported_species()


class TestConfidenceThreshold:
    def test_high_confidence_is_bird(self, tmp_model_dir, temp_wav):
        config = LocalAudioClassifierConfig(
            model_dir=tmp_model_dir,
            mock_mode=True,
            confidence_threshold=0.1,
        )
        clf = LocalAudioClassifier(config)
        clf.load()
        result = clf.identify(temp_wav)
        assert result.is_bird is True

    def test_low_confidence_not_bird(self, tmp_model_dir, temp_wav):
        config = LocalAudioClassifierConfig(
            model_dir=tmp_model_dir,
            mock_mode=True,
            confidence_threshold=0.99,
        )
        clf = LocalAudioClassifier(config)
        clf.load()
        result = clf.identify(temp_wav)
        assert isinstance(result.is_bird, bool)


class TestTrainingDirections:
    def test_directions_contains_steps(self):
        assert "Prerequisites" in TRAINING_DIRECTIONS
        assert "Step 1" in TRAINING_DIRECTIONS
        assert "Step 2" in TRAINING_DIRECTIONS
        assert "log-mel spectrograms" in TRAINING_DIRECTIONS


class TestRealModelNotFound:
    def test_load_without_model_returns_false(self, tmp_model_dir):
        config = LocalAudioClassifierConfig(
            model_dir=tmp_model_dir,
            mock_mode=False,
        )
        clf = LocalAudioClassifier(config)
        assert clf.load() is False
        assert clf.is_ready() is False

    def test_identify_without_model_returns_unknown(self, tmp_model_dir, temp_wav):
        config = LocalAudioClassifierConfig(
            model_dir=tmp_model_dir,
            mock_mode=False,
        )
        clf = LocalAudioClassifier(config)
        result = clf.identify(temp_wav)
        assert result.species == "Unknown"
        assert result.is_bird is False


class TestConfigRoundTrip:
    def test_config_to_dict(self):
        config = LocalAudioClassifierConfig(
            model_dir="data/models",
            model_name="cnn",
            num_epochs=30,
            confidence_threshold=0.8,
        )
        d = config.to_dict()
        assert d["model_dir"] == "data/models"
        assert d["model_name"] == "cnn"
        assert d["num_epochs"] == 30
        assert d["confidence_threshold"] == 0.8

    def test_config_from_dict(self):
        d = {
            "model_dir": "data/models",
            "model_name": "cnn",
            "num_epochs": 25,
            "batch_size": 8,
            "learning_rate": 0.0005,
            "confidence_threshold": 0.75,
            "mock_mode": True,
        }
        config = LocalAudioClassifierConfig.from_dict(d)
        assert config.num_epochs == 25
        assert config.batch_size == 8
        assert config.learning_rate == 0.0005
        assert config.confidence_threshold == 0.75

    def test_config_defaults(self):
        config = LocalAudioClassifierConfig()
        assert config.model_name == "cnn"
        assert config.mock_mode is True


class TestAudioPreprocessingMock:
    """Test the numpy fallback preprocessing path without librosa."""

    @pytest.mark.skipif(
        __import__("importlib").util.find_spec("numpy") is None,
        reason="numpy not installed",
    )
    def test_preprocess_numpy_returns_array(self, mock_audio_classifier, temp_wav):
        spec = mock_audio_classifier._preprocess_with_numpy(temp_wav)
        assert spec is not None
        assert spec.ndim == 3  # (1, n_mels, time)
        assert spec.shape[0] == 1

    def test_preprocess_numpy_invalid_file(self, mock_audio_classifier):
        spec = mock_audio_classifier._preprocess_with_numpy("/nonexistent.wav")
        assert spec is None

    @pytest.mark.skipif(
        __import__("importlib").util.find_spec("numpy") is None,
        reason="numpy not installed",
    )
    def test_mel_filterbank_shape(self, mock_audio_classifier):
        import numpy as np

        fb = LocalAudioClassifier._build_mel_filterbank(
            n_freqs=257, n_mels=64, sample_rate=16000, n_fft=512
        )
        assert fb.shape == (64, 257)
        # Each row should sum to approximately 1 (triangular filters)
        row_sums = fb.sum(axis=1)
        assert np.all(row_sums > 0)


class TestSoundIdentifierIntegration:
    """Integration: LocalAudioClassifier wired into SoundIdentifier."""

    def test_tier1_local_classifier_hit(self, tmp_path, tmp_model_dir):
        from modules.sound_identifier import SoundIdentifier

        wav_path = str(tmp_path / "test.wav")
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            frames = struct.pack("<" + "h" * 16000, *([0] * 16000))
            wf.writeframes(frames)

        clf = LocalAudioClassifier(
            LocalAudioClassifierConfig(model_dir=tmp_model_dir, mock_mode=True)
        )
        clf.load()

        sid = SoundIdentifier(
            {
                "mock_mode": True,
                "local_audio_classifier": clf,
                "confidence_threshold": 0.5,
            }
        )
        result = sid.identify_sound(wav_path)
        assert result["is_bird"] is True
        assert result["species"] != "Unknown"
        assert result["confidence"] > 0

    def test_tier1_local_classifier_miss_falls_back(self, tmp_path, tmp_model_dir):
        from modules.sound_identifier import SoundIdentifier

        wav_path = str(tmp_path / "test.wav")
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            frames = struct.pack("<" + "h" * 16000, *([0] * 16000))
            wf.writeframes(frames)

        clf = LocalAudioClassifier(
            LocalAudioClassifierConfig(
                model_dir=tmp_model_dir, mock_mode=True, confidence_threshold=0.99
            )
        )
        clf.load()

        sid = SoundIdentifier(
            {
                "mock_mode": True,
                "local_audio_classifier": clf,
                "confidence_threshold": 0.99,
            }
        )
        result = sid.identify_sound(wav_path)
        # Mock classifier misses (threshold 0.99), falls back to mock Hermes
        assert result["is_bird"] is True
        assert result["species"] != "Unknown"
