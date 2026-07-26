"""tests/test_review_queue.py"""

from datetime import datetime, timezone

import pytest
from core.types import BirdSighting, RarityLevel
from modules.review_queue import ReviewQueue

@pytest.fixture
def queue():
    return ReviewQueue(confidence_threshold=0.7)

@pytest.fixture
def low_confidence_sighting():
    return BirdSighting(
        species="Unknown Sparrow",
        confidence=0.45,
        rarity_level=RarityLevel.COMMON,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

@pytest.fixture
def high_confidence_sighting():
    return BirdSighting(
        species="American Robin",
        confidence=0.95,
        rarity_level=RarityLevel.COMMON,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

class TestReviewQueue:
    def test_should_review_low_confidence(self, queue, low_confidence_sighting):
        assert queue.should_review(low_confidence_sighting) is True
    def test_should_not_review_high_confidence(self, queue, high_confidence_sighting):
        assert queue.should_review(high_confidence_sighting) is False
    def test_add_for_review(self, queue, low_confidence_sighting):
        assert queue.add_for_review(low_confidence_sighting) is True
        assert queue.pending_count == 1
    def test_get_next(self, queue, low_confidence_sighting):
        queue.add_for_review(low_confidence_sighting)
        item = queue.get_next()
        assert item is not None
        assert item.status == "pending"
    def test_confirm(self, queue, low_confidence_sighting):
        queue.add_for_review(low_confidence_sighting)
        item = queue.get_next()
        assert queue.confirm(item.sighting_id) is True
    def test_correct(self, queue, low_confidence_sighting):
        queue.add_for_review(low_confidence_sighting)
        item = queue.get_next()
        assert queue.correct(item.sighting_id, "Song Sparrow") is True
    def test_reject(self, queue, low_confidence_sighting):
        queue.add_for_review(low_confidence_sighting)
        item = queue.get_next()
        assert queue.reject(item.sighting_id) is True
    def test_stats(self, queue, low_confidence_sighting):
        queue.add_for_review(low_confidence_sighting)
        item = queue.get_next()
        queue.confirm(item.sighting_id)
        stats = queue.get_stats()
        assert stats["confirmed"] == 1
    def test_review_history(self, queue, low_confidence_sighting):
        queue.add_for_review(low_confidence_sighting)
        item = queue.get_next()
        queue.confirm(item.sighting_id)
        history = queue.get_review_history()
        assert len(history) == 1
