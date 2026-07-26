"""tests/test_confidence_calibrator.py — Confidence calibrator tests."""

import pytest

from core.types import IdentificationResult
from modules.confidence_calibrator import ConfidenceCalibrator


@pytest.fixture
def calibrator():
    return ConfidenceCalibrator()


class TestRecordFeedback:
    def test_record_correct(self, calibrator):
        calibrator.record_feedback("Robin", correct=True, confidence=0.9)
        stats = calibrator.get_species_accuracy("Robin")
        assert stats["total"] == 1
        assert stats["correct"] == 1

    def test_record_incorrect(self, calibrator):
        calibrator.record_feedback("Robin", correct=False, confidence=0.9)
        stats = calibrator.get_species_accuracy("Robin")
        assert stats["accuracy"] == 0.0


class TestCalibrate:
    def test_no_data_returns_original(self, calibrator):
        result = IdentificationResult(species="Robin", confidence=0.9)
        calibrated = calibrator.calibrate(result)
        assert calibrated.confidence == 0.9

    def test_insufficient_samples(self, calibrator):
        calibrator.record_feedback("Robin", correct=True, confidence=0.9)
        calibrator.record_feedback("Robin", correct=True, confidence=0.9)
        result = IdentificationResult(species="Robin", confidence=0.9)
        calibrated = calibrator.calibrate(result)
        assert calibrated.confidence == 0.9  # Not enough samples (need 3)

    def test_calibrate_overconfident(self, calibrator):
        # Model says 0.9 confidence but is only right 50% of the time
        for _ in range(3):
            calibrator.record_feedback("Robin", correct=True, confidence=0.9)
        for _ in range(3):
            calibrator.record_feedback("Robin", correct=False, confidence=0.9)
        result = IdentificationResult(species="Robin", confidence=0.9)
        calibrated = calibrator.calibrate(result)
        # Should be lower than original
        assert calibrated.confidence < 0.9

    def test_calibrate_accurate(self, calibrator):
        for _ in range(5):
            calibrator.record_feedback("Robin", correct=True, confidence=0.8)
        result = IdentificationResult(species="Robin", confidence=0.8)
        calibrated = calibrator.calibrate(result)
        # Should be higher (100% accuracy / 80% avg confidence = 1.25x)
        assert calibrated.confidence >= 0.8


class TestStats:
    def test_empty_stats(self, calibrator):
        stats = calibrator.get_all_stats()
        assert stats["global_total"] == 0

    def test_global_stats(self, calibrator):
        calibrator.record_feedback("Robin", correct=True, confidence=0.9)
        calibrator.record_feedback("Crow", correct=False, confidence=0.8)
        stats = calibrator.get_all_stats()
        assert stats["global_total"] == 2
        assert stats["global_correct"] == 1
        assert stats["species_count"] == 2
