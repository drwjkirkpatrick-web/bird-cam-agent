"""
modules/confidence_calibrator.py — Identification confidence calibration.

NOTE: Adjusts confidence scores from the Hermes bridge based on historical
      accuracy. If the bridge consistently over-identifies a species (high
      confidence but wrong), this module lowers the effective confidence.
      If it's usually right, confidence stays high.

WHY: Vision LLMs can be overconfident. A calibration layer that learns from
     user feedback (confirmed/corrected identifications) improves the
     reliability of alerts over time.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from core.types import IdentificationResult

logger = logging.getLogger(__name__)


class ConfidenceCalibrator:
    """
    Calibrates identification confidence based on historical accuracy.

    Usage:
        calibrator = ConfidenceCalibrator()
        # User confirms a sighting was correct
        calibrator.record_feedback("American Robin", correct=True, confidence=0.92)
        # User corrects a misidentification
        calibrator.record_feedback("American Robin", correct=False, confidence=0.85)
        # Apply calibration to a new result
        adjusted = calibrator.calibrate(result)
    """

    def __init__(self):
        self._feedback: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"correct": 0, "total": 0, "confidence_sum": 0.0}
        )
        self._min_samples = 3  # Need at least N samples before calibrating
        self._global_correct = 0
        self._global_total = 0

    def record_feedback(
        self, species: str, correct: bool, confidence: float
    ) -> None:
        """
        Record user feedback on an identification.

        Args:
            species: The species that was identified
            correct: Whether the identification was correct
            confidence: The original confidence score from the LLM
        """
        entry = self._feedback[species]
        entry["total"] += 1
        entry["confidence_sum"] += confidence
        if correct:
            entry["correct"] += 1
            self._global_correct += 1
        self._global_total += 1

        logger.debug(
            "Feedback recorded: %s correct=%s confidence=%.2f (species accuracy: %.0f%%)",
            species, correct, confidence,
            (entry["correct"] / entry["total"] * 100) if entry["total"] > 0 else 0,
        )

    def calibrate(self, result: IdentificationResult) -> IdentificationResult:
        """
        Apply calibration to an identification result.

        Returns a new IdentificationResult with adjusted confidence.
        """
        species = result.species
        entry = self._feedback.get(species)

        if entry is None or entry["total"] < self._min_samples:
            # Not enough data — return original confidence
            return result

        # Compute species-specific accuracy
        accuracy = entry["correct"] / entry["total"]

        # Compute average confidence for this species
        avg_confidence = entry["confidence_sum"] / entry["total"]

        # NOTE: Calibration factor: if the model is usually right but
        # overconfident, scale down. If it's usually wrong, scale down more.
        if avg_confidence > 0:
            calibration_factor = accuracy / avg_confidence
        else:
            calibration_factor = 1.0

        # Clamp to [0, 1.5] — allow up to 50% boost for very accurate species
        calibration_factor = max(0.0, min(1.5, calibration_factor))

        adjusted_confidence = result.confidence * calibration_factor
        adjusted_confidence = max(0.0, min(1.0, adjusted_confidence))

        # Return a new result with adjusted confidence
        return IdentificationResult(
            species=result.species,
            scientific_name=result.scientific_name,
            confidence=adjusted_confidence,
            is_bird=result.is_bird,
            attributes=result.attributes,
            description=result.description,
            alternative_species=result.alternative_species,
            timestamp=result.timestamp,
        )

    def get_species_accuracy(self, species: str) -> dict[str, Any]:
        """Get accuracy statistics for a specific species."""
        entry = self._feedback.get(species)
        if entry is None or entry["total"] == 0:
            return {
                "species": species,
                "total": 0,
                "correct": 0,
                "accuracy": 0.0,
                "avg_confidence": 0.0,
                "calibrated": False,
            }

        return {
            "species": species,
            "total": entry["total"],
            "correct": entry["correct"],
            "accuracy": round(entry["correct"] / entry["total"], 3),
            "avg_confidence": round(entry["confidence_sum"] / entry["total"], 3),
            "calibrated": entry["total"] >= self._min_samples,
        }

    def get_all_stats(self) -> dict[str, Any]:
        """Get calibration statistics for all species."""
        species_stats = {}
        for species in self._feedback:
            species_stats[species] = self.get_species_accuracy(species)

        global_accuracy = (
            self._global_correct / self._global_total
            if self._global_total > 0
            else 0.0
        )

        return {
            "global_accuracy": round(global_accuracy, 3),
            "global_total": self._global_total,
            "global_correct": self._global_correct,
            "species_count": len(self._feedback),
            "calibrated_species": sum(
                1 for s in self._feedback.values() if s["total"] >= self._min_samples
            ),
            "species_stats": species_stats,
        }

    def reset(self) -> None:
        """Clear all calibration data."""
        self._feedback.clear()
        self._global_correct = 0
        self._global_total = 0


__all__ = ["ConfidenceCalibrator"]