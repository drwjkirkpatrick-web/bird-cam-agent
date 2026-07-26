"""
modules/review_queue.py — Human review queue for low-confidence identifications.

NOTE: Queues low-confidence or uncertain identifications for human review.
      The user can confirm, correct, or reject each identification, building
      a training dataset that improves the confidence calibrator.

WHY: Bird Buddy lets users correct misidentifications. This module creates
     a review queue where the user can verify uncertain IDs, improving
     accuracy over time via the confidence_calibrator module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.types import BirdSighting

logger = logging.getLogger(__name__)


@dataclass
class ReviewItem:
    """A single item in the review queue."""
    sighting_id: str
    species: str
    confidence: float
    photo_path: str
    timestamp: str
    status: str = "pending"  # pending, confirmed, corrected, rejected
    corrected_species: str = ""
    reviewer_notes: str = ""


class ReviewQueue:
    """
    Queue for human review of uncertain identifications.

    Usage:
        queue = ReviewQueue(confidence_threshold=0.7)
        queue.add_for_review(sighting)
        item = queue.get_next()
        queue.confirm(item.sighting_id)
        queue.correct(item.sighting_id, "Dark-eyed Junco")
    """

    def __init__(self, confidence_threshold: float = 0.7):
        self._queue: list[ReviewItem] = []
        self._threshold = confidence_threshold
        self._reviewed_count = 0

    def should_review(self, sighting: BirdSighting) -> bool:
        """Check if a sighting should be queued for review."""
        return sighting.confidence < self._threshold

    def add_for_review(self, sighting: BirdSighting) -> bool:
        """Add a sighting to the review queue if confidence is low."""
        if not self.should_review(sighting):
            return False

        item = ReviewItem(
            sighting_id=sighting.sighting_id,
            species=sighting.species,
            confidence=sighting.confidence,
            photo_path=sighting.photo_path,
            timestamp=sighting.timestamp,
        )
        self._queue.append(item)
        logger.info("Added to review queue: %s (confidence: %.0f%%)",
                     sighting.species, sighting.confidence)
        return True

    def get_next(self) -> ReviewItem | None:
        """Get the next pending review item."""
        for item in self._queue:
            if item.status == "pending":
                return item
        return None

    def get_pending(self) -> list[ReviewItem]:
        """Get all pending review items."""
        return [item for item in self._queue if item.status == "pending"]

    def confirm(self, sighting_id: str) -> bool:
        """Confirm an identification as correct."""
        item = self._find(sighting_id)
        if item and item.status == "pending":
            item.status = "confirmed"
            self._reviewed_count += 1
            logger.info("Confirmed: %s", item.species)
            return True
        return False

    def correct(self, sighting_id: str, correct_species: str, notes: str = "") -> bool:
        """Correct a misidentification."""
        item = self._find(sighting_id)
        if item and item.status == "pending":
            item.status = "corrected"
            item.corrected_species = correct_species
            item.reviewer_notes = notes
            self._reviewed_count += 1
            logger.info("Corrected: %s -> %s", item.species, correct_species)
            return True
        return False

    def reject(self, sighting_id: str, notes: str = "") -> bool:
        """Reject an identification (not a bird, or unidentifiable)."""
        item = self._find(sighting_id)
        if item and item.status == "pending":
            item.status = "rejected"
            item.reviewer_notes = notes
            self._reviewed_count += 1
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Return review queue statistics."""
        confirmed = sum(1 for i in self._queue if i.status == "confirmed")
        corrected = sum(1 for i in self._queue if i.status == "corrected")
        rejected = sum(1 for i in self._queue if i.status == "rejected")
        pending = sum(1 for i in self._queue if i.status == "pending")
        return {
            "total": len(self._queue),
            "pending": pending,
            "confirmed": confirmed,
            "corrected": corrected,
            "rejected": rejected,
            "reviewed": self._reviewed_count,
            "accuracy": round(confirmed / max(self._reviewed_count, 1), 3),
        }

    def get_review_history(self) -> list[dict[str, Any]]:
        """Get all reviewed items."""
        return [
            {
                "sighting_id": item.sighting_id,
                "original_species": item.species,
                "corrected_species": item.corrected_species,
                "status": item.status,
                "confidence": item.confidence,
                "notes": item.reviewer_notes,
            }
            for item in self._queue if item.status != "pending"
        ]

    def _find(self, sighting_id: str) -> ReviewItem | None:
        """Find a review item by sighting ID."""
        for item in self._queue:
            if item.sighting_id == sighting_id:
                return item
        return None

    @property
    def pending_count(self) -> int:
        return sum(1 for i in self._queue if i.status == "pending")


__all__ = ["ReviewQueue", "ReviewItem"]
