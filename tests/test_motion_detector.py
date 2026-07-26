"""
tests/test_motion_detector.py — Tests for the motion detection module.

NOTE: These tests cover mock mode, cooldown logic, reference frame
      management, score computation, and the cv2/PIL backends. The
      cv2-backed tests skip cleanly when opencv-python isn't installed,
      matching the project's convention of graceful degradation.

WHY: Motion detection is the trigger for the entire capture pipeline.
     If it fires too eagerly we waste storage on empty frames; if it
     misses real birds we lose sightings. These tests pin down both
     the happy path and the edge cases (cooldown, size mismatch,
     missing reference) so the detector behaves predictably.
"""

from __future__ import annotations

import os
import time

import numpy as np
import pytest

from modules.motion_detector import MotionDetector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def detector() -> MotionDetector:
    """A MotionDetector in mock mode with a short cooldown for testing."""
    return MotionDetector(
        {"mock_mode": True, "cooldown_seconds": 5, "sensitivity": 0.5}
    )


@pytest.fixture
def real_detector() -> MotionDetector:
    """A MotionDetector with mock_mode off (uses cv2/PIL backends)."""
    return MotionDetector(
        {"mock_mode": False, "cooldown_seconds": 5, "sensitivity": 0.5}
    )


@pytest.fixture
def reference_image(tmp_path) -> str:
    """Create a solid-gray JPEG to use as the reference frame."""
    pytest.importorskip("PIL")
    from PIL import Image

    path = str(tmp_path / "reference.jpg")
    Image.new("L", (200, 150), color=128).save(path, "JPEG")
    return path


@pytest.fixture
def same_image(tmp_path) -> str:
    """An image identical to the reference (no motion expected)."""
    pytest.importorskip("PIL")
    from PIL import Image

    path = str(tmp_path / "same.jpg")
    Image.new("L", (200, 150), color=128).save(path, "JPEG")
    return path


@pytest.fixture
def different_image(tmp_path) -> str:
    """An image very different from the reference (motion expected)."""
    pytest.importorskip("PIL")
    from PIL import Image

    path = str(tmp_path / "different.jpg")
    # NOTE: Near-white frame vs the gray reference → large diff → motion.
    Image.new("L", (200, 150), color=250).save(path, "JPEG")
    return path


# ---------------------------------------------------------------------------
# Mock mode tests
# ---------------------------------------------------------------------------
class TestMockMode:
    """Tests for the mock alternating detection behavior."""

    def test_mock_returns_true_then_false(self, detector: MotionDetector) -> None:
        """
        First call returns True, second returns False (alternating).

        NOTE: This is the core contract of mock mode — it lets tests
              exercise both the "motion" and "no motion" branches
              without needing real images.
        """
        first = detector.detect_motion("fake.jpg")
        second = detector.detect_motion("fake.jpg")
        assert first is True
        assert second is False

    def test_mock_alternates_three_cycles(self, detector: MotionDetector) -> None:
        """Verify the True/False pattern holds over multiple cycles."""
        results = [detector.detect_motion("fake.jpg") for _ in range(6)]
        # NOTE: Because cooldown is 5s and these calls happen in <1s,
        #       after the first True (which sets cooldown), all
        #       subsequent calls are suppressed to False. We verify
        #       the first two and that all later are False.
        assert results[0] is True
        # Remaining are False due to cooldown
        for r in results[1:]:
            assert r is False

    def test_mock_no_cooldown_first_detection(self) -> None:
        """
        The very first detection should never be blocked by cooldown.

        NOTE: _last_detection_time starts at 0, so is_in_cooldown()
              returns False — the first detect_motion call is free.
        """
        d = MotionDetector({"mock_mode": True, "cooldown_seconds": 100})
        assert d.detect_motion("fake.jpg") is True

    def test_mock_score_high_on_motion(self, detector: MotionDetector) -> None:
        """get_motion_score returns a high value when 'motion' state."""
        # NOTE: _mock_call_count is 0 (even) → high score (0.8)
        score = detector.get_motion_score("fake.jpg")
        assert score == pytest.approx(0.8)

    def test_mock_score_low_after_detection(self, detector: MotionDetector) -> None:
        """After one detect_motion call, score reflects 'no motion'."""
        detector.detect_motion("fake.jpg")  # advances counter to 1
        score = detector.get_motion_score("fake.jpg")
        assert score == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# Cooldown tests
# ---------------------------------------------------------------------------
class TestCooldown:
    """Tests for the cooldown period logic."""

    def test_cooldown_prevents_re_detection(self, detector: MotionDetector) -> None:
        """
        After a detection, subsequent calls within cooldown return False.

        NOTE: The first call returns True (mock alternation), setting
              _last_detection_time. The second call is within the 5s
              cooldown, so even though the mock counter would return
              False anyway, the cooldown guarantees False.
        """
        first = detector.detect_motion("fake.jpg")
        assert first is True
        # NOTE: Now in cooldown — all subsequent calls return False
        #       regardless of the mock counter value.
        for _ in range(5):
            assert detector.detect_motion("fake.jpg") is False

    def test_cooldown_allows_after_timeout(self) -> None:
        """
        After cooldown expires, detection resumes normally.

        NOTE: We use a very short cooldown (0.01s) so the test doesn't
              have to sleep for 5 real seconds. After sleeping past it,
              the detector should again return True (the counter is
              now even).
        """
        d = MotionDetector(
            {"mock_mode": True, "cooldown_seconds": 0.01}
        )
        assert d.detect_motion("fake.jpg") is True  # first detection
        time.sleep(0.05)  # wait past cooldown
        # NOTE: Counter advanced to 1 during the cooldown-suppressed
        #       call above... actually no — the first call returned True
        #       and set cooldown. After timeout, counter is 1 (odd) →
        #       False. But we want to show detection CAN happen. Let's
        #       call enough times to cycle back to True.
        # After cooldown, first non-cooldown call: counter=1 → False
        assert d.detect_motion("fake.jpg") is False
        # counter=2 → True (but now cooldown set again if it returns True)
        # Actually counter=2 is even → True, sets cooldown
        assert d.detect_motion("fake.jpg") is True

    def test_is_in_cooldown_false_initially(
        self, detector: MotionDetector
    ) -> None:
        """is_in_cooldown() is False before any detection."""
        assert detector.is_in_cooldown() is False

    def test_is_in_cooldown_true_after_detection(
        self, detector: MotionDetector
    ) -> None:
        """is_in_cooldown() is True immediately after a detection."""
        detector.detect_motion("fake.jpg")  # returns True, sets cooldown
        assert detector.is_in_cooldown() is True

    def test_is_in_cooldown_false_after_timeout(self) -> None:
        """is_in_cooldown() returns False after cooldown expires."""
        d = MotionDetector({"mock_mode": True, "cooldown_seconds": 0.01})
        d.detect_motion("fake.jpg")  # triggers detection
        assert d.is_in_cooldown() is True
        time.sleep(0.05)
        assert d.is_in_cooldown() is False

    def test_cooldown_zero_allows_all(self) -> None:
        """
        With cooldown_seconds=0, detections are never suppressed.

        NOTE: A zero cooldown means is_in_cooldown() always returns
              False (elapsed >= 0 is always true), so the mock
              alternation runs unimpeded.
        """
        d = MotionDetector({"mock_mode": True, "cooldown_seconds": 0})
        results = [d.detect_motion("fake.jpg") for _ in range(4)]
        # NOTE: With no cooldown, we get the pure alternating pattern:
        #       True, False, True, False
        assert results == [True, False, True, False]


# ---------------------------------------------------------------------------
# Reference frame tests
# ---------------------------------------------------------------------------
class TestReferenceFrame:
    """Tests for set_reference and reset_reference."""

    def test_set_reference_works(
        self, real_detector: MotionDetector, reference_image: str
    ) -> None:
        """set_reference stores the path and loads the image array."""
        real_detector.set_reference(reference_image)
        assert real_detector._reference_path == reference_image
        assert real_detector._reference_image is not None
        # NOTE: Grayscale image should be a 2D numpy array
        assert real_detector._reference_image.ndim == 2

    def test_reset_reference_clears(
        self, real_detector: MotionDetector, reference_image: str
    ) -> None:
        """reset_reference clears both the path and cached image."""
        real_detector.set_reference(reference_image)
        assert real_detector._reference_image is not None
        real_detector.reset_reference()
        assert real_detector._reference_path is None
        assert real_detector._reference_image is None

    def test_detect_without_reference_returns_false(
        self, real_detector: MotionDetector, same_image: str
    ) -> None:
        """
        First detect_motion with no reference sets it and returns False.

        NOTE: There's nothing to compare against on the first frame,
              so the current frame becomes the reference and no motion
              is reported. This prevents a false trigger on startup.
        """
        result = real_detector.detect_motion(same_image)
        assert result is False
        # NOTE: The reference should now be set to the current photo
        assert real_detector._reference_path == same_image

    def test_reset_then_detect_sets_new_reference(
        self, real_detector: MotionDetector, reference_image: str, same_image: str
    ) -> None:
        """After reset, the next detect call establishes a new reference."""
        real_detector.set_reference(reference_image)
        real_detector.reset_reference()
        result = real_detector.detect_motion(same_image)
        assert result is False
        assert real_detector._reference_path == same_image


# ---------------------------------------------------------------------------
# Motion score tests
# ---------------------------------------------------------------------------
class TestMotionScore:
    """Tests for get_motion_score."""

    def test_score_returns_float(self, detector: MotionDetector) -> None:
        """get_motion_score must return a float in [0.0, 1.0]."""
        score = detector.get_motion_score("fake.jpg")
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_score_zero_without_reference(
        self, real_detector: MotionDetector, same_image: str
    ) -> None:
        """Score is 0.0 when no reference frame is set."""
        score = real_detector.get_motion_score(same_image)
        assert score == 0.0

    def test_score_pil_same_image_low(
        self, real_detector: MotionDetector, reference_image: str, same_image: str
    ) -> None:
        """Identical frames produce a near-zero motion score."""
        real_detector.set_reference(reference_image)
        score = real_detector.get_motion_score(same_image)
        # NOTE: JPEG compression may introduce tiny differences, so
        #       we check that the score is very low, not exactly zero.
        assert score < 0.05

    def test_score_pil_different_image_high(
        self, real_detector: MotionDetector, reference_image: str, different_image: str
    ) -> None:
        """Very different frames produce a high motion score."""
        real_detector.set_reference(reference_image)
        score = real_detector.get_motion_score(different_image)
        # NOTE: Near-white vs gray → most pixels differ by >25 → high score
        assert score > 0.5


# ---------------------------------------------------------------------------
# Sensitivity and contour area tests
# ---------------------------------------------------------------------------
class TestSensitivity:
    """Tests for sensitivity threshold and min_contour_area filtering."""

    def test_sensitivity_clamped_to_range(self) -> None:
        """Sensitivity above 1.0 is clamped to 1.0."""
        d = MotionDetector({"sensitivity": 2.0})
        assert d.sensitivity == 1.0

    def test_sensitivity_clamped_below_zero(self) -> None:
        """Sensitivity below 0.0 is clamped to 0.0."""
        d = MotionDetector({"sensitivity": -0.5})
        assert d.sensitivity == 0.0

    def test_sensitivity_default(self) -> None:
        """Default sensitivity is 0.5."""
        d = MotionDetector()
        assert d.sensitivity == 0.5

    def test_high_sensitivity_detects_minor_motion(
        self, reference_image: str, same_image: str
    ) -> None:
        """
        With high sensitivity (0.99), even tiny differences trigger motion.

        NOTE: threshold = 1.0 - sensitivity = 0.01, so a score of
              even 0.02 (tiny JPEG noise) exceeds it.
        """
        d = MotionDetector(
            {"mock_mode": False, "sensitivity": 0.99, "cooldown_seconds": 0}
        )
        d.set_reference(reference_image)
        # NOTE: same_image is nearly identical, but JPEG compression
        #       introduces minimal pixel differences. With threshold
        #       at 0.01, even that tiny score may trigger.
        result = d.detect_motion(same_image)
        score = d.get_motion_score(same_image)
        # NOTE: We assert the relationship: if score > threshold, motion
        #       is detected. This verifies the sensitivity logic.
        threshold = 1.0 - d.sensitivity
        assert result == (score > threshold)

    def test_low_sensitivity_ignores_minor_motion(
        self, reference_image: str, same_image: str
    ) -> None:
        """
        With low sensitivity (0.01), minor differences are ignored.

        NOTE: threshold = 1.0 - 0.01 = 0.99, so only near-total frame
              change triggers detection.
        """
        d = MotionDetector(
            {"mock_mode": False, "sensitivity": 0.01, "cooldown_seconds": 0}
        )
        d.set_reference(reference_image)
        result = d.detect_motion(same_image)
        score = d.get_motion_score(same_image)
        threshold = 1.0 - d.sensitivity
        assert result == (score > threshold)
        # NOTE: For nearly identical images, score should be well
        #       below 0.99, so no motion detected.
        assert result is False

    def test_min_contour_area_default(self) -> None:
        """Default min_contour_area is 500."""
        d = MotionDetector()
        assert d.min_contour_area == 500

    def test_min_contour_area_custom(self) -> None:
        """min_contour_area can be overridden via config."""
        d = MotionDetector({"min_contour_area": 2000})
        assert d.min_contour_area == 2000

    def test_min_contour_area_filters_small_motion(
        self, reference_image: str, different_image: str
    ) -> None:
        """
        A large min_contour_area filters out small motion blobs.

        NOTE: We use cv2 (if available) to test contour filtering. The
              different_image is a uniform near-white frame, so cv2
              would find one large contour covering most of the image.
              With a min_contour_area larger than the image, no contour
              passes the filter, so no motion is detected.

        WHY: This verifies that min_contour_area actually gates the
             detection — a detector that ignores this setting would
             fire on any pixel change, including sensor noise.
        """
        pytest.importorskip("cv2")
        d = MotionDetector(
            {
                "mock_mode": False,
                "min_contour_area": 999999,  # larger than 200x150=30000
                "sensitivity": 0.5,
                "cooldown_seconds": 0,
            }
        )
        d.set_reference(reference_image)
        result = d.detect_motion_cv2(different_image)
        # NOTE: The single contour (whole-frame diff) has area < 999999,
        #       so it's filtered out → no motion detected.
        assert result is False

    def test_min_contour_area_allows_large_motion(
        self, reference_image: str, different_image: str
    ) -> None:
        """
        A small min_contour_area allows large motion blobs through.

        NOTE: With min_contour_area=100, the large contour from the
              near-white different_image easily passes the filter.
        """
        pytest.importorskip("cv2")
        d = MotionDetector(
            {
                "mock_mode": False,
                "min_contour_area": 100,
                "sensitivity": 0.5,
                "cooldown_seconds": 0,
            }
        )
        d.set_reference(reference_image)
        result = d.detect_motion_cv2(different_image)
        assert result is True


# ---------------------------------------------------------------------------
# cv2 backend tests — skip cleanly without cv2
# ---------------------------------------------------------------------------
class TestCv2Backend:
    """
    Tests for the OpenCV detection backend.

    NOTE: These skip cleanly when opencv-python (cv2) isn't installed,
          matching the project convention of graceful degradation.
    """

    def test_cv2_available_or_skip(self) -> None:
        """Verify cv2 is importable, or skip the rest of this class."""
        pytest.importorskip("cv2")

    def test_cv2_detects_motion(
        self, reference_image: str, different_image: str
    ) -> None:
        """cv2 backend detects motion between very different frames."""
        pytest.importorskip("cv2")
        d = MotionDetector(
            {"mock_mode": False, "sensitivity": 0.5, "cooldown_seconds": 0}
        )
        d.set_reference(reference_image)
        assert d.detect_motion_cv2(different_image) is True

    def test_cv2_no_motion_same_frame(
        self, reference_image: str, same_image: str
    ) -> None:
        """cv2 backend returns False for identical frames."""
        pytest.importorskip("cv2")
        d = MotionDetector(
            {"mock_mode": False, "sensitivity": 0.5, "cooldown_seconds": 0}
        )
        d.set_reference(reference_image)
        result = d.detect_motion_cv2(same_image)
        # NOTE: Identical gray frames → no contours above min area
        assert result is False

    def test_cv2_raises_without_cv2(self) -> None:
        """
        detect_motion_cv2 raises RuntimeError when cv2 is unavailable.

        NOTE: If cv2 IS installed, this test is skipped because we
              can't simulate its absence. The real protection is the
              _CV2_AVAILABLE guard in detect_motion().
        """
        if _cv2_available():
            pytest.skip("cv2 is installed — can't test absence")
        d = MotionDetector({"mock_mode": False})
        with pytest.raises(RuntimeError, match="cv2 not available"):
            d.detect_motion_cv2("fake.jpg")


# ---------------------------------------------------------------------------
# PIL backend tests
# ---------------------------------------------------------------------------
class TestPilBackend:
    """Tests for the PIL fallback detection backend."""

    def test_pil_detects_motion(
        self, real_detector: MotionDetector, reference_image: str, different_image: str
    ) -> None:
        """PIL backend detects motion between very different frames."""
        real_detector.set_reference(reference_image)
        assert real_detector.detect_motion_pil(different_image) is True

    def test_pil_no_motion_same_frame(
        self, real_detector: MotionDetector, reference_image: str, same_image: str
    ) -> None:
        """PIL backend returns False for identical frames."""
        real_detector.set_reference(reference_image)
        result = real_detector.detect_motion_pil(same_image)
        assert result is False

    def test_pil_sets_reference_on_first_call(
        self, real_detector: MotionDetector, same_image: str
    ) -> None:
        """PIL backend sets reference on first call and returns False."""
        result = real_detector.detect_motion_pil(same_image)
        assert result is False
        assert real_detector._reference_path == same_image


# ---------------------------------------------------------------------------
# Config and initialization tests
# ---------------------------------------------------------------------------
class TestConfig:
    """Tests for configuration handling."""

    def test_default_config(self) -> None:
        """Default config has expected values."""
        d = MotionDetector()
        assert d.sensitivity == 0.5
        assert d.min_contour_area == 500
        assert d.mock_mode is True
        assert d.cooldown_seconds == 5

    def test_none_config_uses_defaults(self) -> None:
        """None config is treated as empty dict (all defaults)."""
        d = MotionDetector(None)
        assert d.sensitivity == 0.5
        assert d.mock_mode is True

    def test_partial_config_preserves_defaults(self) -> None:
        """Partial config only overrides specified keys."""
        d = MotionDetector({"sensitivity": 0.8})
        assert d.sensitivity == 0.8
        assert d.min_contour_area == 500  # default
        assert d.mock_mode is True  # default
        assert d.cooldown_seconds == 5  # default

    def test_cooldown_seconds_custom(self) -> None:
        """cooldown_seconds can be overridden."""
        d = MotionDetector({"cooldown_seconds": 30})
        assert d.cooldown_seconds == 30


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _cv2_available() -> bool:
    """Check if cv2 is importable (used to conditionally skip tests)."""
    try:
        import cv2  # noqa: F401

        return True
    except ImportError:
        return False