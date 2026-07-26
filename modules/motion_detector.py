"""
modules/motion_detector.py — Motion detection for Bird Cam Agent.

NOTE: This module compares the current camera frame against a stored
      reference frame to determine whether motion (and thus a bird)
      is present. It supports two backends: OpenCV (cv2) for high-
      performance absdiff + contour detection, and a PIL fallback
      for environments without cv2. A mock mode is provided for
      development and testing without real images.

WHY: Motion detection is the trigger for the entire capture pipeline.
     Without it, the agent would either capture continuously (wasting
     storage and battery) or rely on a fixed interval (missing fast-
     moving birds). By detecting motion first, we capture only when
     something interesting is in frame.

FEATURES:
  - cv2.absdiff + contour detection (preferred, fast)
  - PIL pixel-difference fallback (works without cv2)
  - Mock mode with alternating True/False for testing both paths
  - Cooldown period to prevent rapid-fire redundant detections
  - Configurable sensitivity and minimum contour area
  - Motion score (0.0-1.0) for graduated response
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# NOTE: cv2 (opencv-python) is an optional dependency. We guard the
#       import so this module loads on machines without OpenCV —
#       the PIL fallback or mock mode will be used instead.
# WHY: The agent must run on dev laptops and CI runners that don't
#      have opencv-python installed. Guarding the import means
#      `from modules.motion_detector import MotionDetector` never
#      crashes, even when cv2 is absent.
try:
    import cv2

    _CV2_AVAILABLE: bool = True
except ImportError:
    # NOTE: Typed as Any so Pyright doesn't flag cv2.* attribute access
    #       in the methods below — at runtime _CV2_AVAILABLE is False
    #       and those code paths are never reached.
    cv2: Any = None  # type: ignore[assignment]
    _CV2_AVAILABLE = False


class MotionDetector:
    """
    Detect motion by comparing the current frame to a reference frame.

    Usage:
        detector = MotionDetector({"mock_mode": False, "sensitivity": 0.7})
        detector.set_reference("reference.jpg")
        if detector.detect_motion("current.jpg"):
            # motion detected — trigger capture
            ...

    NOTE: In mock_mode (default True), detect_motion() alternates
          True/False/True/False on successive calls so tests can
          exercise both the "motion detected" and "no motion" code
          paths without needing real images.

    WHY: Alternating mock output is more useful than always-True or
         always-False because it lets the orchestrator and downstream
         modules be tested against both outcomes from a single
         fixture. A detector that only ever returns True can't
         verify the "no motion" branch of the caller.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the motion detector.

        Args:
            config: Optional dict with keys:
                sensitivity (float): 0.0-1.0, higher = more sensitive.
                    Default 0.5.
                min_contour_area (int): Minimum contour area in pixels
                    to count as motion. Default 500.
                mock_mode (bool): If True, use mock detection.
                    Default True.
                cooldown_seconds (float): Minimum seconds between
                    detections. Default 5.

        NOTE: All config keys are optional — missing keys fall back
              to defaults. This makes it easy to override just one
              setting (e.g. {"sensitivity": 0.8}) without specifying
              the full config.
        """
        config = config or {}
        self.sensitivity: float = float(config.get("sensitivity", 0.5))
        self.min_contour_area: int = int(config.get("min_contour_area", 500))
        self.mock_mode: bool = bool(config.get("mock_mode", True))
        self.cooldown_seconds: float = float(config.get("cooldown_seconds", 5))

        # NOTE: Clamp sensitivity to [0.0, 1.0] so invalid config can't
        #       produce nonsensical thresholds downstream.
        self.sensitivity = max(0.0, min(1.0, self.sensitivity))

        # Reference frame state
        self._reference_path: str | None = None
        # NOTE: Cached grayscale array so we don't re-read the reference
        #       file on every detect_motion call.
        self._reference_image: np.ndarray | None = None

        # Cooldown state
        # NOTE: 0.0 means "never detected" — is_in_cooldown() returns
        #       False when this is 0, so the very first detection is
        #       never blocked by a phantom cooldown.
        self._last_detection_time: float = 0.0

        # Mock alternating counter
        # NOTE: Advances on every detect_motion call (even during
        #       cooldown) so the True/False pattern stays predictable
        #       regardless of cooldown timing.
        self._mock_call_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def detect_motion(self, photo_path: str) -> bool:
        """
        Return True if motion is detected in *photo_path*.

        NOTE: In mock mode, returns alternating True/False/True/False
              on successive calls (respecting cooldown). In real mode,
              tries cv2 first, then falls back to PIL.

        WHY: Cooldown is checked first so we don't fire on every frame
             of a bird that's been sitting on the feeder for 30 seconds.
             The caller gets a clean boolean and doesn't need to
             separately check is_in_cooldown().
        """
        if self.mock_mode:
            return self._detect_mock()

        # --- Real mode ---
        # NOTE: Check cooldown before doing any image work — if we're
        #       in cooldown, skip the expensive comparison entirely.
        if self.is_in_cooldown():
            return False

        # Try cv2 first (fastest, most accurate)
        if _CV2_AVAILABLE:
            try:
                return self.detect_motion_cv2(photo_path)
            except Exception as e:
                # WHY: cv2 might fail on a corrupt image or shape
                #      mismatch. Log and fall through to PIL rather
                #      than crashing the whole pipeline.
                logger.warning("cv2 detection failed (%s) — trying PIL", e)

        # PIL fallback
        try:
            return self.detect_motion_pil(photo_path)
        except Exception as e:
            logger.error("PIL detection also failed: %s", e)
            return False

    def set_reference(self, photo_path: str) -> None:
        """
        Set the reference frame for comparison.

        NOTE: The image is loaded immediately and cached as a grayscale
              numpy array so subsequent detect_motion calls don't
              re-read the file. If the file can't be loaded, the
              reference path is still stored — real detection will
              treat the next frame as the new reference.

        WHY: Caching the array avoids disk I/O on every frame
             comparison, which matters when the camera is capturing
             at 1-2 fps and the reference is a large image.
        """
        self._reference_path = photo_path
        self._reference_image = self._load_grayscale(photo_path)
        logger.debug("Reference frame set: %s", photo_path)

    def reset_reference(self) -> None:
        """
        Clear the reference frame.

        NOTE: After calling this, the next detect_motion call (in real
              mode) will treat the current photo as the new reference
              and return False — no motion on the first frame.
        """
        self._reference_path = None
        self._reference_image = None
        logger.debug("Reference frame cleared")

    def detect_motion_cv2(self, photo_path: str) -> bool:
        """
        Detect motion using OpenCV absdiff + contour analysis.

        NOTE: Requires cv2 (opencv-python). If cv2 is not installed,
              this method raises RuntimeError — the caller (detect_motion)
              catches that and falls back to PIL.

        WHY: cv2.absdiff is the fastest and most accurate way to compute
             frame differences. Contour filtering lets us ignore noise
             (small pixel changes from sensor jitter) and focus on real
             objects (birds) that produce large contiguous contours.
        """
        if not _CV2_AVAILABLE:
            raise RuntimeError("cv2 not available")

        # NOTE: If no reference is set, the current frame becomes the
        #       reference and we return False — there's nothing to
        #       compare against on the very first frame.
        if self._reference_image is None:
            self.set_reference(photo_path)
            return False

        current = self._load_grayscale(photo_path)
        if current is None:
            logger.warning("Could not load current frame: %s", photo_path)
            return False

        # NOTE: Ensure both frames are the same size; if not, resize
        #       the current to match the reference so absdiff doesn't
        #       raise a shape-mismatch error.
        if current.shape != self._reference_image.shape:
            current = cv2.resize(
                current,
                (self._reference_image.shape[1], self._reference_image.shape[0]),
            )

        # absdiff highlights pixel-level changes between frames
        diff = cv2.absdiff(self._reference_image, current)
        # NOTE: Threshold at 25 to suppress low-level sensor noise.
        #       Pixels that changed by less than 25 levels are ignored.
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        # Dilate to merge nearby contours (reduces fragmentation)
        thresh = cv2.dilate(thresh, None, iterations=2)
        # Find external contours
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # NOTE: Filter contours by min_contour_area — small blobs are
        #       likely noise (leaves blowing, sensor jitter), not birds.
        motion_area = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= self.min_contour_area:
                motion_area += area

        total_area = float(current.shape[0] * current.shape[1])
        score = motion_area / total_area if total_area > 0 else 0.0

        # NOTE: sensitivity maps to a score threshold: higher
        #       sensitivity → lower threshold → more likely to detect.
        #       threshold = 1.0 - sensitivity.
        detected = score > (1.0 - self.sensitivity)
        if detected:
            self._last_detection_time = time.time()
        return detected

    def detect_motion_pil(self, photo_path: str) -> bool:
        """
        Detect motion using PIL image difference (fallback for no cv2).

        NOTE: This is slower than cv2 but works with only Pillow
              installed. It compares grayscale pixel arrays directly
              and counts the fraction of "significantly changed" pixels.

        WHY: Not every deployment has opencv-python (it's a heavy
             dependency, especially on ARM). PIL is already required
             for the mock camera, so this fallback adds zero new deps.
        """
        if self._reference_image is None:
            self.set_reference(photo_path)
            return False

        current = self._load_grayscale(photo_path)
        if current is None:
            return False

        # NOTE: Ensure shapes match — if the current frame is a different
        #       size, crop or pad to the reference dimensions. This is a
        #       rough fallback; cv2.resize (in detect_motion_cv2) is
        #       the proper way to handle size mismatches.
        if current.shape != self._reference_image.shape:
            h, w = self._reference_image.shape[:2]
            ch, cw = current.shape[:2]
            h_min, w_min = min(h, ch), min(w, cw)
            ref = self._reference_image[:h_min, :w_min]
            cur = current[:h_min, :w_min]
        else:
            ref = self._reference_image
            cur = current

        # NOTE: Use int16 to avoid uint8 overflow when subtracting.
        diff = np.abs(ref.astype(np.int16) - cur.astype(np.int16))
        # Pixels with difference > 25 are "changed"
        changed = diff > 25
        total = changed.size
        score = float(np.count_nonzero(changed)) / float(total) if total > 0 else 0.0

        detected = score > (1.0 - self.sensitivity)
        if detected:
            self._last_detection_time = time.time()
        return detected

    def is_in_cooldown(self) -> bool:
        """
        Return True if within the cooldown period after last detection.

        NOTE: Cooldown prevents rapid-fire detections from the same
              bird. If no detection has ever occurred
              (_last_detection_time is 0), this returns False — the
              first detection is never blocked.

        WHY: Without cooldown, a bird sitting on the feeder for 10
             seconds at 2 fps would trigger 20 captures of the same
             bird. Cooldown ensures we only trigger once per
             cooldown_seconds window.
        """
        if self._last_detection_time == 0:
            return False
        elapsed = time.time() - self._last_detection_time
        return elapsed < self.cooldown_seconds

    def get_motion_score(self, photo_path: str) -> float:
        """
        Return a 0.0-1.0 motion intensity score.

        NOTE: In mock mode, returns a deterministic value (0.8 for
              "motion" state, 0.1 for "no motion") without advancing
              the mock counter or checking cooldown. In real mode,
              computes the actual frame-difference score.

        WHY: A graduated score (rather than just True/False) lets the
             caller decide how to respond — e.g. "high score → start
             video recording, low score → single photo only".
        """
        if self.mock_mode:
            # NOTE: Even count → high score (motion), odd → low (no
            #       motion). This mirrors what the next detect_motion
            #       call would return, so callers can peek at the
            #       score before committing to a detection.
            return 0.8 if self._mock_call_count % 2 == 0 else 0.1

        if self._reference_image is None:
            return 0.0

        # Try cv2 first
        if _CV2_AVAILABLE:
            try:
                current = self._load_grayscale(photo_path)
                if current is None:
                    return 0.0
                if current.shape != self._reference_image.shape:
                    current = cv2.resize(
                        current,
                        (self._reference_image.shape[1], self._reference_image.shape[0]),
                    )
                diff = cv2.absdiff(self._reference_image, current)
                _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                return (
                    float(np.count_nonzero(thresh)) / float(thresh.size)
                    if thresh.size > 0
                    else 0.0
                )
            except Exception as e:
                logger.warning("cv2 score failed: %s", e)

        # PIL fallback
        try:
            current = self._load_grayscale(photo_path)
            if current is None:
                return 0.0
            if current.shape != self._reference_image.shape:
                h, w = self._reference_image.shape[:2]
                ch, cw = current.shape[:2]
                h_min, w_min = min(h, ch), min(w, cw)
                ref = self._reference_image[:h_min, :w_min]
                cur = current[:h_min, :w_min]
            else:
                ref = self._reference_image
                cur = current
            diff = np.abs(ref.astype(np.int16) - cur.astype(np.int16))
            changed = diff > 25
            total = changed.size
            return float(np.count_nonzero(changed)) / float(total) if total > 0 else 0.0
        except Exception as e:
            logger.warning("PIL score failed: %s", e)
            return 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _detect_mock(self) -> bool:
        """
        Mock detection: alternating True/False with cooldown.

        NOTE: The counter advances on every call (even during cooldown)
              so the alternating pattern stays predictable regardless
              of cooldown timing. Cooldown is checked first — if in
              cooldown, return False immediately (but still advance
              the counter).

        WHY: Advancing the counter during cooldown means that after
             cooldown expires, the next non-cooldown call lands on a
             predictable parity. If we froze the counter during
             cooldown, tests would need to know exactly how many
             cooldown-suppressed calls occurred to predict the next
             real result — fragile and confusing.
        """
        if self.is_in_cooldown():
            # NOTE: Still advance the counter so the alternating
            #       pattern resumes correctly after cooldown expires.
            self._mock_call_count += 1
            return False

        detected = self._mock_call_count % 2 == 0
        self._mock_call_count += 1
        if detected:
            self._last_detection_time = time.time()
        return detected

    def _load_grayscale(self, photo_path: str) -> np.ndarray | None:
        """
        Load an image as a grayscale numpy array.

        NOTE: Tries cv2 first (faster), then PIL. Returns None if
              the file can't be loaded or doesn't exist.

        WHY: Both cv2 and PIL can read common image formats, but cv2
             returns a numpy array directly while PIL requires a
             np.array() conversion. Trying cv2 first saves a step
             when it's available.
        """
        if not os.path.exists(photo_path):
            logger.warning("Photo not found: %s", photo_path)
            return None

        if _CV2_AVAILABLE:
            img = cv2.imread(photo_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                return img
            logger.warning("cv2.imread returned None for %s", photo_path)

        try:
            from PIL import Image

            img = Image.open(photo_path).convert("L")
            return np.array(img)
        except Exception as e:
            logger.error("Failed to load %s: %s", photo_path, e)
            return None


__all__ = ["MotionDetector"]


# NOTE: Add has_reference property for compatibility
def _has_reference(self) -> bool:
    """Whether a reference frame is set."""
    return self._reference_path is not None

MotionDetector.has_reference = property(_has_reference)