"""
modules/recorder.py — Video recorder module for the Bird Cam Agent.

NOTE: This module provides a family of video recorders behind a common
      abstract interface. The orchestrator doesn't care whether the video
      comes from a Pi Camera, a USB webcam, or a mock — it just calls
      start_recording() and later stop_recording() to get a file path.

WHY: Hardware abstraction lets the same code run on a Raspberry Pi with
     a Pi Camera (picamera), on any machine with a USB webcam (OpenCV),
     or on a dev laptop with no camera at all (MockRecorder). The
     RecorderFactory picks the right backend from CameraConfig, so the
     rest of the agent never branches on hardware type.

DESIGN: Recording happens in a background thread so the orchestrator loop
        isn't blocked while video is captured. start_recording() spawns the
        thread; stop_recording() signals it to stop and joins. A
        threading.Lock protects the shared recording state and file path so
        concurrent calls (e.g. a timer firing while the user stops manually)
        can't corrupt state. A threading.Event lets stop_recording() wake the
        recording thread early instead of waiting for the full duration.
"""

from __future__ import annotations

import logging
import os
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from core.types import CameraConfig

logger = logging.getLogger(__name__)

# NOTE: Guard the optional hardware libraries at import time so this module
#       loads on any machine — a dev laptop without picamera or cv2 can still
#       import MockRecorder and RecorderFactory. Each hardware recorder checks
#       its flag in __init__ and raises a clear RuntimeError if the library is
#       missing, so misuse fails loudly instead of with an obscure ImportError
#       deep inside a recording thread.
try:
    import picamera  # type: ignore
    _PICAMERA_AVAILABLE = True
except ImportError:
    picamera = None  # type: ignore
    _PICAMERA_AVAILABLE = False

try:
    import cv2  # type: ignore
    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore
    _CV2_AVAILABLE = False


class RecorderBase(ABC):
    """
    Abstract base class for all video recorders.

    NOTE: Every subclass takes a CameraConfig in __init__ and implements
          start_recording, stop_recording, is_recording, and the protected
          _record hook that does the actual hardware-specific capture.

    WHY: A single abstract interface lets the orchestrator and tests treat
         all recorders uniformly. The shared thread/lifecycle logic lives
         here in protected helpers so subclasses stay small and focused on
         hardware concerns.

    Thread model:
        - start_recording() spawns a daemon thread running _record().
        - stop_recording() sets a stop Event and joins the thread.
        - is_recording() reports the current state under the lock.
        - The lock guards _recording and _file_path; the Event signals
          early stop. Never touch _recording/_file_path without the lock.
    """

    def __init__(self, config: CameraConfig):
        self.config = config
        # NOTE: One lock guards the shared recording state and file path.
        #       All reads/writes of _recording and _file_path go through it.
        self._lock = threading.Lock()
        self._recording = False
        self._thread: threading.Thread | None = None
        # WHY: An Event (not a bare bool) lets stop_recording() wake a
        #      recording thread that's sleeping/waiting on duration so it
        #      can exit immediately instead of blocking for the full length.
        self._stop_event = threading.Event()
        self._file_path: str = ""

    # ---- shared helpers (called by subclass abstractmethod impls) ----

    def _generate_filename(self) -> str:
        """
        Build a timestamped .mp4 path under config.video_dir.

        NOTE: Format is recording_{YYYYMMDD_HHMMSS}.mp4. The timestamp is
              local time — videos are for human review, so local time is
              more meaningful than UTC for a single-location bird cam.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.config.video_dir, f"recording_{timestamp}.mp4")

    def _ensure_video_dir(self) -> None:
        """Create the video output directory if it doesn't exist."""
        os.makedirs(self.config.video_dir, exist_ok=True)

    def _begin_recording(self, duration_sec: float) -> str:
        """
        Shared start logic: reset stop flag, claim a file path, spawn the
        recording thread. Returns the planned file path.

        NOTE: Called by each subclass's start_recording() implementation.
              Holds the lock while flipping state so is_recording() can't
              observe a half-started recorder.
        """
        if duration_sec <= 0:
            raise ValueError("duration_sec must be positive")

        with self._lock:
            if self._recording:
                # WHY: Refuse a double-start rather than silently clobbering
                #      an in-flight recording — the caller likely has a bug.
                raise RuntimeError("Recording already in progress")
            self._ensure_video_dir()
            self._stop_event.clear()
            self._file_path = self._generate_filename()
            path = self._file_path
            self._recording = True
            # NOTE: daemon=True so a forgotten stop_recording() can't keep
            #       the process alive at shutdown.
            self._thread = threading.Thread(
                target=self._record,
                args=(duration_sec,),
                daemon=True,
                name=f"{type(self).__name__}-record",
            )
            self._thread.start()
        logger.info(
            "%s started recording %.1fs -> %s",
            type(self).__name__,
            duration_sec,
            path,
        )
        return path

    def _end_recording(self) -> str:
        """
        Shared stop logic: signal the thread to stop, join it, mark not
        recording. Returns the file path (or "" if nothing was recording).

        NOTE: Called by each subclass's stop_recording() implementation.
              Joins with a timeout so a wedged hardware thread can't hang
              the caller forever.
        """
        with self._lock:
            if not self._recording:
                # WHY: stop without start is a no-op returning "" — graceful
                #      handling per the spec, not an error.
                return ""
            path = self._file_path
            thread = self._thread
            self._stop_event.set()

        if thread is not None:
            # NOTE: Join outside the lock so the recording thread — which
            #       needs the lock in some paths — can't deadlock against
            #       us. A generous timeout guards against hung hardware.
            thread.join(timeout=30.0)
            if thread.is_alive():
                logger.warning(
                    "Recording thread did not stop within 30s — continuing"
                )

        with self._lock:
            self._recording = False
            self._thread = None
            self._stop_event.clear()
            final_path = self._file_path
            self._file_path = ""

        logger.info("%s stopped recording -> %s", type(self).__name__, final_path)
        return final_path

    def _is_recording_locked(self) -> bool:
        """Shared is_recording logic: read the flag under the lock."""
        with self._lock:
            return self._recording

    def _was_stopped(self) -> bool:
        """True if stop_recording() has been called for the current clip."""
        return self._stop_event.is_set()

    # ---- abstract API (the spec-required surface) ----

    @abstractmethod
    def start_recording(self, duration_sec: float) -> str:
        """
        Begin recording in a background thread. Returns the planned file
        path (the file is finalized when recording stops).
        """
        ...

    @abstractmethod
    def stop_recording(self) -> str:
        """
        Stop the in-flight recording, join its thread, and return the file
        path. Returns "" if nothing was recording.
        """
        ...

    @abstractmethod
    def is_recording(self) -> bool:
        """Return True if a recording is currently in progress."""
        ...

    # ---- subclass hook ----

    @abstractmethod
    def _record(self, duration_sec: float) -> None:
        """
        Hardware-specific capture loop, run on the recording thread.

        NOTE: Implementations must check self._was_stopped() periodically
              so stop_recording() can end the clip early. They should
              finalize the output file before returning.
        """
        ...


class MockRecorder(RecorderBase):
    """
    Mock recorder that writes a placeholder .mp4 file — no camera needed.

    NOTE: This is the default backend when mock_mode is True or no hardware
          library is available. It exercises the full thread/lifecycle path
          (start, background timing, stop, file output) so the orchestrator
          and tests can run end-to-end without a camera.

    WHY: A real .mp4 isn't needed for development — we just need a valid
         file path with .mp4 extension that downstream code (storage,
         notifications) can reference. Writing a few bytes keeps the file
         real on disk so existence/size checks behave like production.
    """

    # NOTE: A small recognizable header so a mock file is easy to identify
    #       by content during debugging. Not a valid mp4 — deliberately.
    _MOCK_HEADER = b"BIRD_CAM_MOCK_VIDEO_v1\n"

    def start_recording(self, duration_sec: float) -> str:
        return self._begin_recording(duration_sec)

    def stop_recording(self) -> str:
        return self._end_recording()

    def is_recording(self) -> bool:
        return self._is_recording_locked()

    def _record(self, duration_sec: float) -> None:
        """
        Sleep for the requested duration (or until stopped early), then
        write a placeholder file. The file is always written on exit so
        stop_recording() yields a path even if the duration was cut short.
        """
        # NOTE: Wait on the stop Event with the full duration as timeout.
        #       If stop_recording() fires, wait() returns True immediately
        #       and we skip to file writing. Otherwise it times out after
        #       duration_sec and we proceed naturally.
        self._stop_event.wait(timeout=duration_sec)

        path = ""
        with self._lock:
            path = self._file_path
        if path:
            try:
                with open(path, "wb") as f:
                    f.write(self._MOCK_HEADER)
                    # NOTE: Timestamp + duration metadata for debugging.
                    f.write(
                        f"recorded={datetime.now().isoformat()} "
                        f"duration={duration_sec}s\n".encode()
                    )
            except OSError as e:
                logger.error("MockRecorder failed to write %s: %s", path, e)


class PiCameraRecorder(RecorderBase):
    """
    Raspberry Pi Camera recorder using the picamera library.

    NOTE: Requires the `picamera` package and a Pi Camera connected to the
          CSI port. If picamera isn't importable, __init__ raises a clear
          RuntimeError so the factory can fall back rather than crash.

    WHY: picamera gives direct, low-latency access to the Pi Camera's
         hardware H.264 encoder, producing real .mp4 files far more
         efficiently than a USB webcam path on the Pi.
    """

    def __init__(self, config: CameraConfig):
        super().__init__(config)
        if not _PICAMERA_AVAILABLE:
            # NOTE: Fail loudly at construction, not on first recording, so
            #       the factory can choose a different backend immediately.
            raise RuntimeError(
                "PiCameraRecorder requires the 'picamera' library, which is "
                "not installed. Install it on a Raspberry Pi or use mock/usb."
            )

    def start_recording(self, duration_sec: float) -> str:
        return self._begin_recording(duration_sec)

    def stop_recording(self) -> str:
        return self._end_recording()

    def is_recording(self) -> bool:
        return self._is_recording_locked()

    def _record(self, duration_sec: float) -> None:
        """
        Record H.264 video to the file path using picamera.

        NOTE: picamera's start_recording/wait_recording/stop_recording
              pattern is used. wait_recording is called in a loop so we can
              check _was_stopped() for an early stop instead of blocking
              for the whole duration.
        """
        path = ""
        with self._lock:
            path = self._file_path
        if not path:
            return

        camera = None
        try:
            # NOTE: picamera.PiCamera is a context manager, but we manage it
            #       manually here so we can call stop_recording on early exit.
            camera = picamera.PiCamera()  # type: ignore[union-attr]
            camera.resolution = (
                self.config.resolution_width,
                self.config.resolution_height,
            )
            camera.start_recording(path, format="mp4")
            logger.info("PiCamera recording to %s", path)

            # WHY: Loop in 0.5s chunks so stop_recording() is responsive.
            elapsed = 0.0
            chunk = 0.5
            while elapsed < duration_sec and not self._was_stopped():
                wait = min(chunk, duration_sec - elapsed)
                camera.wait_recording(wait)
                elapsed += wait
            camera.stop_recording()
        except Exception as e:
            logger.error("PiCamera recording failed: %s", e)
            # NOTE: Attempt to stop cleanly even on error so partial files
            #       are flushed.
            if camera is not None:
                try:
                    camera.stop_recording()
                except Exception:
                    pass
        finally:
            if camera is not None:
                try:
                    camera.close()
                except Exception:
                    pass


class USBRecorder(RecorderBase):
    """
    USB webcam recorder using OpenCV (cv2.VideoWriter).

    NOTE: Requires the `opencv-python` package and a USB webcam available
          at config.device_index. If cv2 isn't importable, __init__ raises
          a clear RuntimeError.

    WHY: OpenCV's VideoCapture/VideoWriter work with any UVC webcam and
         run on x86 laptops as well as Pi, making it the portable hardware
         backend. The frame loop checks _was_stopped() each iteration for
         responsive early stops.
    """

    def __init__(self, config: CameraConfig):
        super().__init__(config)
        if not _CV2_AVAILABLE:
            raise RuntimeError(
                "USBRecorder requires the 'opencv-python' (cv2) library, "
                "which is not installed. Install it or use mock mode."
            )

    def start_recording(self, duration_sec: float) -> str:
        return self._begin_recording(duration_sec)

    def stop_recording(self) -> str:
        return self._end_recording()

    def is_recording(self) -> bool:
        return self._is_recording_locked()

    def _record(self, duration_sec: float) -> None:
        """
        Capture frames from the webcam and write them to an .mp4 file.

        NOTE: Uses cv2.VideoCapture(device_index) and cv2.VideoWriter with
              the mp4v fourcc. The loop reads frames until the duration
              elapses or stop_recording() sets the stop Event.
        """
        path = ""
        with self._lock:
            path = self._file_path
        if not path:
            return

        cap = None
        writer = None
        try:
            cap = cv2.VideoCapture(self.config.device_index)  # type: ignore[union-attr]
            if not cap.isOpened():
                logger.error(
                    "USBRecorder: cannot open camera at index %d",
                    self.config.device_index,
                )
                return

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))  # type: ignore[union-attr]
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))  # type: ignore[union-attr]
            fps = 20.0  # NOTE: Fixed target fps; real webcams vary.
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[union-attr]
            writer = cv2.VideoWriter(path, fourcc, fps, (width, height))  # type: ignore[union-attr]

            start = datetime.now()
            frame_interval = 1.0 / fps
            while not self._was_stopped():
                elapsed = (datetime.now() - start).total_seconds()
                if elapsed >= duration_sec:
                    break
                ret, frame = cap.read()
                if not ret:
                    logger.warning("USBRecorder: frame read failed, ending early")
                    break
                writer.write(frame)
        except Exception as e:
            logger.error("USBRecorder recording failed: %s", e)
        finally:
            if writer is not None:
                try:
                    writer.release()
                except Exception:
                    pass
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass


class RecorderFactory:
    """
    Selects the right RecorderBase implementation for a CameraConfig.

    NOTE: All methods are static — the factory is stateless. Use it as
          RecorderFactory.create(config).

    WHY: Centralizing backend selection here means the orchestrator never
         imports hardware libraries or branches on camera_type. The factory
         also implements graceful fallback: if a requested backend's
         library isn't installed, it falls back to MockRecorder instead of
         crashing, so the agent degrades gracefully on a dev machine.
    """

    @staticmethod
    def create(config: CameraConfig) -> RecorderBase:
        """
        Build a recorder matching the config.

        Selection rules:
          - camera_type == "mock" or mock_mode True -> MockRecorder
          - camera_type == "picamera" -> PiCameraRecorder (falls back to
            MockRecorder if picamera isn't installed)
          - camera_type == "usb" -> USBRecorder (falls back to
            MockRecorder if cv2 isn't installed)
          - camera_type == "auto" -> PiCamera if available, else USB if
            available, else MockRecorder
        """
        ctype = (config.camera_type or "auto").lower()

        # NOTE: mock_mode short-circuits everything — it's the universal
        #       "run without hardware" flag, checked first.
        if config.mock_mode or ctype == "mock":
            logger.info("RecorderFactory: using MockRecorder (mock_mode=%s)", config.mock_mode)
            return MockRecorder(config)

        if ctype == "picamera":
            if _PICAMERA_AVAILABLE:
                try:
                    return PiCameraRecorder(config)
                except RuntimeError as e:
                    logger.warning("PiCameraRecorder unavailable (%s) — falling back to mock", e)
            else:
                logger.warning("picamera not installed — falling back to MockRecorder")
            return MockRecorder(config)

        if ctype == "usb":
            if _CV2_AVAILABLE:
                try:
                    return USBRecorder(config)
                except RuntimeError as e:
                    logger.warning("USBRecorder unavailable (%s) — falling back to mock", e)
            else:
                logger.warning("cv2 not installed — falling back to MockRecorder")
            return MockRecorder(config)

        if ctype == "auto":
            # NOTE: Prefer the Pi Camera on a Pi (better quality/latency),
            #       then a USB webcam, then mock as the last resort.
            if _PICAMERA_AVAILABLE:
                try:
                    return PiCameraRecorder(config)
                except RuntimeError:
                    pass
            if _CV2_AVAILABLE:
                try:
                    return USBRecorder(config)
                except RuntimeError:
                    pass
            logger.info("RecorderFactory: no hardware backend available — using MockRecorder")
            return MockRecorder(config)

        # NOTE: Unknown camera_type -> safe default rather than raising.
        logger.warning("Unknown camera_type %r — defaulting to MockRecorder", ctype)
        return MockRecorder(config)


# NOTE: __all__ documents the public API and keeps star-imports clean.
__all__ = [
    "RecorderBase",
    "MockRecorder",
    "PiCameraRecorder",
    "USBRecorder",
    "RecorderFactory",
]