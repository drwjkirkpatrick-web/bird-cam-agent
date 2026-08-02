"""
modules/identifier.py — High-level bird identification coordinator.

NOTE: This module wraps the HermesBridge and adds retry logic, confidence
      thresholding, history tracking, and batch processing.

WHY: The HermesBridge is a thin transport layer. BirdIdentifier adds the
     operational concerns: what if the identification fails? What if
     confidence is low? How do we track what we've identified?
"""

from __future__ import annotations

import logging
import time
from typing import Any

from core.config import Config
from core.types import IdentificationResult
from modules.hermes_bridge import HermesBridge

logger = logging.getLogger(__name__)


class BirdIdentifier:
    """
    Coordinates bird identification via the Hermes vision bridge or a local classifier.

    Usage:
        bridge = HermesBridge(config.hermes_bridge)
        identifier = BirdIdentifier(bridge, config)
        result = identifier.identify("data/photos/bird_001.jpg")
        if result.is_bird and result.confidence > 0.7:
            print(f"High-confidence ID: {result.species}")

    Two-tier identification (recommended):
        1. Local classifier (fast, offline) — tries first
        2. Hermes bridge (slow, cloud) — fallback for low-confidence or unknown
    """

    def __init__(
        self,
        hermes_bridge: HermesBridge,
        config: Config,
        local_classifier=None,  # type: ignore  # LocalBirdClassifier, optional
    ):
        self.bridge = hermes_bridge
        self.config = config
        self.local_classifier = local_classifier
        self._history: list[IdentificationResult] = []
        self._max_history = 100
        self._confidence_threshold = config.hermes_bridge.confidence_threshold

        if self.local_classifier is not None and self.local_classifier.is_ready():
            logger.info(
                "BirdIdentifier: local classifier ready (%d species)",
                len(self.local_classifier.get_supported_species()),
            )

    def identify(self, photo_path: str) -> IdentificationResult:
        """
        Identify a bird in a single photo.

        Returns an IdentificationResult. Even if identification fails,
        a valid result is returned (with is_bird=False).
        """
        result = self.identify_with_retry(photo_path)
        self._log_identification(photo_path, result)
        self._add_to_history(result)
        return result

    def identify_batch(
        self, photo_paths: list[str]
    ) -> list[IdentificationResult]:
        """Identify birds in multiple photos sequentially."""
        if not photo_paths:
            return []
        results = []
        for path in photo_paths:
            result = self.identify(path)
            results.append(result)
        return results

    def identify_with_retry(
        self, photo_path: str, max_retries: int = 3
    ) -> IdentificationResult:
        """
        Identify with two-tier strategy: local classifier first, Hermes fallback.

        Tier 1: Local classifier (fast, offline, ~30ms)
        Tier 2: Hermes bridge (slow, cloud, ~2-5s)

        Falls back to Hermes when:
          - local classifier is not loaded
          - confidence below threshold
          - species not in local model's label set
        """
        # ---- Tier 1: Local classifier ----
        if self.local_classifier is not None and self.local_classifier.is_ready():
            result = self.local_classifier.identify(photo_path)
            if result.is_bird and result.confidence >= self._confidence_threshold:
                logger.debug(
                    "Local classifier hit: %s (%.0f%%)",
                    result.species,
                    result.confidence * 100,
                )
                return result
            logger.debug(
                "Local classifier miss/low-confidence: %s (%.0f%%), falling back",
                result.species,
                result.confidence * 100,
            )

        # ---- Tier 2: Hermes bridge ----
        last_result = None
        for attempt in range(max_retries):
            result = self.bridge.identify_bird(photo_path)
            last_result = result

            # Success: we got a bird OR a definitive non-bird
            if result.is_bird:
                return result
            if result.is_bird is False and result.description:
                # Legitimate non-bird detection — don't retry
                return result

            # Transport failure — retry with backoff
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
                logger.warning(
                    "Identification attempt %d failed, retrying in %ds",
                    attempt + 1,
                    wait,
                )
                # NOTE: In mock mode, backoff is skipped for speed
                if self.config.hermes_bridge.mock_mode:
                    continue
                time.sleep(wait)

        logger.error(
            "All %d identification attempts failed for %s",
            max_retries,
            photo_path,
        )
        return last_result or IdentificationResult(
            species="Unknown",
            is_bird=False,
            description="All identification attempts failed",
        )

    def get_identification_history(self) -> list[IdentificationResult]:
        """Return recent identification results (most recent first)."""
        return list(reversed(self._history))

    def clear_history(self) -> None:
        """Clear the in-memory identification history."""
        self._history.clear()

    @property
    def is_low_confidence(self) -> Any:
        """Placeholder — use check_confidence(result) instead."""
        raise AttributeError(
            "Use BirdIdentifier.check_confidence(result) for per-result checks"
        )

    def check_confidence(self, result: IdentificationResult) -> bool:
        """
        Check if a result's confidence is above threshold.

        Returns True if confidence >= threshold, False otherwise.
        """
        return result.confidence >= self._confidence_threshold

    def _log_identification(
        self, photo_path: str, result: IdentificationResult
    ) -> None:
        """Log an identification result."""
        status = "bird" if result.is_bird else "non-bird"
        confidence_str = f"{result.confidence:.0%}" if result.confidence else "N/A"
        logger.info(
            "Identification: %s — %s (%s) confidence=%s photo=%s",
            status,
            result.species,
            result.scientific_name,
            confidence_str,
            photo_path,
        )

    def _add_to_history(self, result: IdentificationResult) -> None:
        """Add a result to the in-memory history (capped at _max_history)."""
        self._history.append(result)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]