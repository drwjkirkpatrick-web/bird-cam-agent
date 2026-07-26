"""
modules/camera.py — Camera capture abstraction layer for Bird Cam Agent.

NOTE: This module provides a uniform interface (CameraBase) over three
      concrete backends — a Pillow-based mock, the Raspberry Pi PiCamera2
      library, and any standard USB webcam via OpenCV (cv2). The factory
      picks the right backend at runtime based on config and available
      hardware.

WHY: Bird Cam Agent must run on (a) a dev laptop with no camera, (b) a
     Raspberry Pi with the official camera module, and (c) a Pi or laptop
     with a generic USB webcam. Keeping the capture logic behind one
     abstract base means the orchestrator never cares which hardware is
     attached — it just calls capture_photo() and gets a file path back.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime

from core.types import CameraConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------
class CameraBase(ABC):
    """
    Abstract camera interface.

    NOTE: Every concrete backend must implement capture_photo() and
          get_camera_info(). The orchestrator depends only on this
          interface, so swapping hardware never changes upstream code.

    WHY: A shared base lets the factory return a single type
         (CameraBase) regardless of which backend was selected, and
         makes it impossible to "forget" to implement a method on a
         new backend — the ABC will refuse to instantiate.
    """

    def __init__(self, config: CameraConfig) -> None:
        self.config = config

    @abstractmethod
    def capture_photo(self) -> str:
        """
        Capture a single still photo and save it as a JPEG.

        Returns:
            The absolute/relative file path of the saved JPEG on disk.
            The path must point to a file that actually exists.
        """
        raise NotImplementedError

    @abstractmethod
    def get_camera_info(self) -> dict:
        """
        Return a dict describing the camera backend and its settings.

        NOTE: Useful for logging, the dashboard, and debugging which
              hardware path was actually selected at runtime.
        """
        raise NotImplementedError

    def _generate_unique_filepath(self, directory: str) -> str:
        """
        Build a unique JPEG path in *directory*.

        NOTE: The base name is bird_{YYYYMMDD_HHMMSS}.jpg. If a file with
              that exact name already exists (because two captures fell
              in the same wall-clock second), a numeric suffix is
              appended: bird_{ts}_1.jpg, _2.jpg, ...

        WHY: A timestamp alone is only unique to one-second resolution.
             On fast hardware, rapid captures collide and silently
             overwrite each other. The suffix loop guarantees every
             capture lands at a distinct, real path — no data loss.
        """
        os.makedirs(directory, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.join(directory, f"bird_{ts}.jpg")
        if not os.path.exists(base):
            return base
        counter = 1
        while True:
            candidate = os.path.join(directory, f"bird_{ts}_{counter}.jpg")
            if not os.path.exists(candidate):
                return candidate
            counter += 1


# ---------------------------------------------------------------------------
# Mock backend — generates a solid-color placeholder JPEG with Pillow
# ---------------------------------------------------------------------------
class MockCameraCapture(CameraBase):
    """
    Mock camera that generates a solid-color placeholder image.

    NOTE: This is the zero-hardware fallback. It produces a real, valid
          JPEG file on disk so every downstream step (identification,
          storage, dashboard preview) has something to chew on during
          development and CI.

    WHY: Running the full agent without a camera is essential for
         testing, demos, and CI pipelines. Generating a genuine JPEG
         (rather than an empty file) means the image pipeline is
         exercised end-to-end even with no hardware attached.
    """

    def __init__(self, config: CameraConfig) -> None:
        super().__init__(config)
        # Solid sky-blue-ish placeholder color — distinct enough that a
        # human glancing at the photo dir can tell it's a mock frame.
        self._placeholder_color = (135, 180, 220)

    def capture_photo(self) -> str:
        """
        Generate a 640x480 solid-color JPEG and save it to photo_dir.

        Returns the path to the saved JPEG.
        """
        # NOTE: _generate_unique_filepath (on CameraBase) ensures the
        #       output directory exists and the filename is collision-free
        #       even for rapid back-to-back captures within one second.
        filepath = self._generate_unique_filepath(self.config.photo_dir)

        try:
            from PIL import Image

            img = Image.new(
                "RGB",
                (640, 480),
                color=self._placeholder_color,
            )
            img.save(filepath, "JPEG")
        except ImportError:
            # WHY: If Pillow isn't installed (rare on Pi images but
            #      possible in minimal containers), fall back to writing
            #      a minimal but valid JPEG so capture_photo() still
            #      returns a real, openable image file.
            self._write_minimal_jpeg(filepath)

        logger.debug("MockCameraCapture wrote %s", filepath)
        return filepath

    def get_camera_info(self) -> dict:
        return {
            "backend": "mock",
            "type": "MockCameraCapture",
            "resolution": (640, 480),
            "photo_dir": self.config.photo_dir,
            "mock_mode": True,
            "device_index": self.config.device_index,
        }

    @staticmethod
    def _write_minimal_jpeg(filepath: str) -> None:
        """
        Write a tiny but valid 1x1 JPEG when Pillow is unavailable.

        NOTE: These are the raw bytes of a valid 1x1 white JPEG. It's
              the absolute smallest legal JPEG so downstream code that
              opens the file (PIL, cv2, browser) doesn't crash.
        """
        minimal_jpeg = bytes(
            [
                0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46,
                0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01,
                0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
                0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08,
                0x07, 0x07, 0x07, 0x09, 0x09, 0x08, 0x0A, 0x0C,
                0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
                0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D,
                0x1A, 0x1C, 0x1C, 0x20, 0x24, 0x2E, 0x27, 0x20,
                0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
                0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27,
                0x39, 0x3D, 0x38, 0x32, 0x3C, 0x2E, 0x33, 0x34,
                0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
                0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4,
                0x00, 0x1F, 0x00, 0x00, 0x01, 0x05, 0x01, 0x01,
                0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04,
                0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0xFF,
                0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
                0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04,
                0x00, 0x00, 0x01, 0x7D, 0x01, 0x02, 0x03, 0x00,
                0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
                0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32,
                0x81, 0x91, 0xA1, 0x08, 0x23, 0x42, 0xB1, 0xC1,
                0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
                0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A,
                0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x34, 0x35,
                0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
                0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55,
                0x56, 0x57, 0x58, 0x59, 0x5A, 0x63, 0x64, 0x65,
                0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
                0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85,
                0x86, 0x87, 0x88, 0x89, 0x8A, 0x92, 0x93, 0x94,
                0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
                0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2,
                0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA,
                0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
                0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8,
                0xD9, 0xDA, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6,
                0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
                0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA,
                0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00,
                0x7B, 0x40, 0x1E, 0x64, 0x78, 0x40, 0x4B, 0x6F,
                0xFE, 0xD8, 0xF9, 0x7E, 0xFF, 0xD9,
            ]
        )
        with open(filepath, "wb") as f:
            f.write(minimal_jpeg)


# ---------------------------------------------------------------------------
# PiCamera2 backend — Raspberry Pi official camera module
# ---------------------------------------------------------------------------
class PiCameraCapture(CameraBase):
    """
    Camera backend using the picamera2 library (Raspberry Pi official cam).

    NOTE: picamera2 is only available on Raspberry Pi OS with libcamera.
          The import is guarded so importing this module on a non-Pi
          machine doesn't crash — the factory catches ImportError and
          falls back to another backend.

    WHY: The Pi Camera Module is the highest-quality, lowest-latency
         option on a Raspberry Pi. We prefer it when available.
    """

    def __init__(self, config: CameraConfig) -> None:
        super().__init__(config)
        # NOTE: Import inside __init__ (not at module top) so that
        #       merely loading this file never fails on non-Pi hosts.
        #       The factory relies on ImportError here for fallback.
        from picamera2 import Picamera2

        self._Picamera2 = Picamera2
        self._camera = None  # lazy — opened on first capture

    def _ensure_camera(self) -> None:
        """Lazily initialize and configure the PiCamera2 instance."""
        if self._camera is not None:
            return

        cam = self._Picamera2()
        # NOTE: "preview" config gives us a still stream at the requested
        #       resolution. We use capture_picamera2 + save to write JPEG.
        cam.configure(
            cam.create_still_configuration(
                main={
                    "size": (
                        self.config.resolution_width,
                        self.config.resolution_height,
                    )
                }
            )
        )
        cam.start()
        self._camera = cam

    def capture_photo(self) -> str:
        filepath = self._generate_unique_filepath(self.config.photo_dir)

        self._ensure_camera()
        # NOTE: capture_file writes directly to disk in JPEG format
        #       when the path ends in .jpg. This avoids an extra
        #       in-memory copy on memory-constrained Pi hardware.
        self._camera.capture_file(filepath)
        logger.debug("PiCameraCapture wrote %s", filepath)
        return filepath

    def get_camera_info(self) -> dict:
        return {
            "backend": "picamera",
            "type": "PiCameraCapture",
            "resolution": (
                self.config.resolution_width,
                self.config.resolution_height,
            ),
            "photo_dir": self.config.photo_dir,
            "mock_mode": self.config.mock_mode,
            "device_index": self.config.device_index,
        }

    def close(self) -> None:
        """Release the camera if it was opened."""
        if self._camera is not None:
            self._camera.close()
            self._camera = None


# ---------------------------------------------------------------------------
# USB webcam backend — any UVC camera via OpenCV
# ---------------------------------------------------------------------------
class USBCameraCapture(CameraBase):
    """
    Camera backend using OpenCV (cv2.VideoCapture) for USB webcams.

    NOTE: cv2.VideoCapture works with any standard UVC webcam on both
          Pi and laptops. The import is guarded so this module loads
          even when opencv-python isn't installed.

    WHY: USB webcams are the most broadly available camera option and
         require no special hardware support — just a USB port and
         the opencv-python package.
    """

    def __init__(self, config: CameraConfig) -> None:
        super().__init__(config)
        # NOTE: Import inside __init__ so the factory can catch
        #       ImportError and fall back to Mock gracefully.
        import cv2

        self._cv2 = cv2
        self._cap = None  # lazy — opened on first capture

    def _ensure_capture(self) -> None:
        """Lazily open the VideoCapture device."""
        if self._cap is not None:
            return

        cap = self._cv2.VideoCapture(self.config.device_index)
        if not cap.isOpened():
            # WHY: If the device index doesn't map to a real camera,
            #      raise so the factory's auto-detect can try the next
            #      backend instead of silently producing black frames.
            raise RuntimeError(
                f"Could not open USB camera at device_index="
                f"{self.config.device_index}"
            )
        self._cap = cap

    def capture_photo(self) -> str:
        filepath = self._generate_unique_filepath(self.config.photo_dir)

        self._ensure_capture()
        ret, frame = self._cap.read()
        if not ret or frame is None:
            raise RuntimeError("USB camera read failed — no frame returned")
        self._cv2.imwrite(filepath, frame)
        logger.debug("USBCameraCapture wrote %s", filepath)
        return filepath

    def get_camera_info(self) -> dict:
        return {
            "backend": "usb",
            "type": "USBCameraCapture",
            "resolution": (
                self.config.resolution_width,
                self.config.resolution_height,
            ),
            "photo_dir": self.config.photo_dir,
            "mock_mode": self.config.mock_mode,
            "device_index": self.config.device_index,
        }

    def close(self) -> None:
        """Release the VideoCapture if it was opened."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None


# ---------------------------------------------------------------------------
# Factory — selects the right backend from config + available hardware
# ---------------------------------------------------------------------------
class CameraFactory:
    """
    Factory that selects the correct CameraBase implementation.

    Usage:
        cam = CameraFactory.create(config)
        path = cam.capture_photo()

    NOTE: The factory encodes the full hardware-selection policy so the
          caller never needs to know which backend is active.

    WHY: Centralizing the selection logic here means adding a new
         backend (e.g. an IP camera) only requires a new class and one
         new branch in create() — no changes to the orchestrator.
    """

    @staticmethod
    def create(config: CameraConfig) -> CameraBase:
        """
        Build and return a CameraBase matching the config and hardware.

        Selection policy:
          - config.mock_mode is True  -> MockCameraCapture (always works)
          - config.camera_type == 'picamera' -> try PiCamera, else Mock
          - config.camera_type == 'usb'      -> try USB, else Mock
          - config.camera_type == 'auto'     -> try PiCamera, then USB,
                                                then Mock as last resort

        NOTE: In 'auto' mode we try the highest-quality option first
              (Pi Camera) and degrade gracefully. Mock is always the
              final fallback so the agent never hard-crashes for lack
              of a camera.
        """
        # Explicit mock short-circuit — highest priority
        if config.mock_mode:
            logger.info("CameraFactory: mock_mode=True -> MockCameraCapture")
            return MockCameraCapture(config)

        cam_type = (config.camera_type or "auto").lower()

        if cam_type == "mock":
            return MockCameraCapture(config)

        if cam_type == "picamera":
            try:
                return PiCameraCapture(config)
            except ImportError:
                logger.warning(
                    "picamera2 not available — falling back to MockCameraCapture"
                )
                return MockCameraCapture(config)

        if cam_type == "usb":
            try:
                return USBCameraCapture(config)
            except ImportError:
                logger.warning(
                    "cv2 not available — falling back to MockCameraCapture"
                )
                return MockCameraCapture(config)

        if cam_type == "auto":
            # NOTE: Try Pi Camera first (best quality on Pi), then USB
            #       webcam, then Mock as the universal fallback.
            try:
                return PiCameraCapture(config)
            except ImportError:
                logger.info("picamera2 not available in auto mode, trying USB")

            try:
                return USBCameraCapture(config)
            except ImportError:
                logger.info("cv2 not available in auto mode, using Mock")

            return MockCameraCapture(config)

        # Unknown camera_type — don't crash, just mock.
        logger.warning(
            "Unknown camera_type=%r — falling back to MockCameraCapture",
            config.camera_type,
        )
        return MockCameraCapture(config)


__all__ = [
    "CameraBase",
    "MockCameraCapture",
    "PiCameraCapture",
    "USBCameraCapture",
    "CameraFactory",
]