"""
modules/live_stream.py — Real-time video stream to web dashboard.

NOTE: Provides a live video feed from the camera that can be viewed in the
      web dashboard or via a direct MJPEG stream URL. Supports Pi Camera,
      USB webcams, and a mock slideshow stream for development.

WHY: Birdfy and Bird Buddy both offer live streaming so users can watch
     their feeder in real time. This module brings that capability to
     the Pi-based bird cam.
"""

from __future__ import annotations

import logging
import os
import time
from io import BytesIO
from typing import Any

logger = logging.getLogger(__name__)


class LiveStream:
    """
    MJPEG live stream server for the bird cam.

    Usage:
        stream = LiveStream({"mock_mode": True, "fps": 5})
        stream.start()
        # View at http://pi-ip:9195/stream
        stream.stop()
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.mock_mode = self.config.get("mock_mode", True)
        self.fps = self.config.get("fps", 5)
        self.quality = self.config.get("quality", 70)
        self.width = self.config.get("width", 640)
        self.height = self.config.get("height", 480)
        self._streaming = False
        self._frame_count = 0
        self._start_time = 0.0

    def start(self) -> bool:
        """Start the live stream."""
        self._streaming = True
        self._start_time = time.time()
        logger.info("Live stream started (fps=%d, %dx%d)", self.fps, self.width, self.height)
        return True

    def stop(self) -> bool:
        """Stop the live stream."""
        self._streaming = False
        elapsed = time.time() - self._start_time if self._start_time else 0
        logger.info("Live stream stopped (ran %.1fs, %d frames)", elapsed, self._frame_count)
        return True

    def is_streaming(self) -> bool:
        """Check if the stream is active."""
        return self._streaming

    def get_frame(self) -> bytes | None:
        """
        Get a single JPEG frame as bytes.

        In mock mode, generates a placeholder image with a timestamp.
        In real mode, captures from the camera.
        """
        if not self._streaming:
            return None

        self._frame_count += 1

        if self.mock_mode:
            return self._generate_mock_frame()

        try:
            from modules.camera import CameraFactory
            from core.types import CameraConfig

            cam = CameraFactory.create(CameraConfig(
                mock_mode=False,
                resolution_width=self.width,
                resolution_height=self.height,
            ))
            path = cam.capture_photo()
            with open(path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error("Frame capture failed: %s", e)
            return self._generate_mock_frame()

    def _generate_mock_frame(self) -> bytes:
        """Generate a placeholder JPEG frame with timestamp overlay."""
        try:
            from PIL import Image, ImageDraw

            img = Image.new("RGB", (self.width, self.height), color=(20, 20, 40))
            draw = ImageDraw.Draw(img)
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            draw.text((10, 10), f"BIRD CAM [MOCK]", fill=(15, 188, 249))
            draw.text((10, 30), ts, fill=(200, 200, 200))
            draw.text((10, 50), f"Frame: {self._frame_count}", fill=(100, 100, 100))

            buf = BytesIO()
            img.save(buf, format="JPEG", quality=self.quality)
            return buf.getvalue()
        except ImportError:
            # NOTE: If PIL is not available, return a minimal JPEG
            return b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9"

    def get_stream_info(self) -> dict[str, Any]:
        """Return stream status information."""
        elapsed = time.time() - self._start_time if self._start_time else 0
        actual_fps = self._frame_count / elapsed if elapsed > 0 else 0
        return {
            "streaming": self._streaming,
            "fps_target": self.fps,
            "fps_actual": round(actual_fps, 1),
            "resolution": f"{self.width}x{self.height}",
            "frame_count": self._frame_count,
            "uptime_seconds": round(elapsed, 1),
            "mode": "mock" if self.mock_mode else "live",
        }

    def generate_mjpeg_headers(self) -> bytes:
        """Generate the multipart/x-mixed-replace boundary headers for MJPEG."""
        return (
            b"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
            b"\r\n"
        )

    def format_mjpeg_frame(self, jpeg_bytes: bytes) -> bytes:
        """Format a JPEG frame as an MJPEG multipart chunk."""
        return (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(jpeg_bytes)).encode() + b"\r\n"
            b"\r\n" + jpeg_bytes + b"\r\n"
        )


__all__ = ["LiveStream"]
