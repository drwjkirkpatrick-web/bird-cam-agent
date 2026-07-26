"""
modules/multi_camera.py — Multi-camera support for multiple angles.

NOTE: Manages multiple cameras pointing at different angles of the feeder.
      Can capture from all cameras simultaneously or round-robin between them.

WHY: A single camera angle may miss birds or get poor lighting. Multiple
     cameras (e.g., one from the front, one from the side) improve
     identification accuracy and capture more behavior.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from core.types import CameraConfig

logger = logging.getLogger(__name__)


@dataclass
class CameraSlot:
    """A named camera slot in a multi-camera setup."""
    name: str
    config: CameraConfig
    enabled: bool = True
    last_capture_path: str = ""


class MultiCameraManager:
    """
    Manages multiple cameras for the bird cam.

    Usage:
        manager = MultiCameraManager()
        manager.add_camera("front", CameraConfig(camera_type="picamera"))
        manager.add_camera("side", CameraConfig(camera_type="usb"))
        photos = manager.capture_all()  # Returns {name: path}
    """

    def __init__(self):
        self._cameras: dict[str, CameraSlot] = {}
        self._lock = threading.Lock()

    def add_camera(self, name: str, config: CameraConfig) -> None:
        """Add a camera to the multi-camera setup."""
        with self._lock:
            self._cameras[name] = CameraSlot(name=name, config=config)
            logger.info("Added camera: %s (type=%s)", name, config.camera_type)

    def remove_camera(self, name: str) -> bool:
        """Remove a camera by name."""
        with self._lock:
            if name in self._cameras:
                del self._cameras[name]
                logger.info("Removed camera: %s", name)
                return True
            return False

    def enable_camera(self, name: str) -> bool:
        """Enable a disabled camera."""
        with self._lock:
            if name in self._cameras:
                self._cameras[name].enabled = True
                return True
            return False

    def disable_camera(self, name: str) -> bool:
        """Disable a camera (skip during captures)."""
        with self._lock:
            if name in self._cameras:
                self._cameras[name].enabled = False
                return True
            return False

    def capture_all(self) -> dict[str, str]:
        """
        Capture from all enabled cameras simultaneously.

        Returns a dict of {camera_name: photo_path}.
        """
        from modules.camera import CameraFactory

        results: dict[str, str] = {}
        threads: list[threading.Thread] = []
        results_lock = threading.Lock()

        def capture_one(slot: CameraSlot) -> None:
            try:
                camera = CameraFactory.create(slot.config)
                path = camera.capture_photo()
                with results_lock:
                    results[slot.name] = path
                    slot.last_capture_path = path
            except Exception as e:
                logger.error("Camera %s capture failed: %s", slot.name, e)

        with self._lock:
            active_slots = [
                slot for slot in self._cameras.values() if slot.enabled
            ]

        for slot in active_slots:
            t = threading.Thread(target=capture_one, args=(slot,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        logger.info("Multi-camera capture: %d/%d cameras succeeded",
                     len(results), len(active_slots))
        return results

    def capture_one(self, name: str) -> str | None:
        """Capture from a single camera by name."""
        with self._lock:
            slot = self._cameras.get(name)
            if slot is None or not slot.enabled:
                return None
            config = slot.config

        from modules.camera import CameraFactory

        try:
            camera = CameraFactory.create(config)
            path = camera.capture_photo()
            with self._lock:
                self._cameras[name].last_capture_path = path
            return path
        except Exception as e:
            logger.error("Camera %s capture failed: %s", name, e)
            return None

    def list_cameras(self) -> list[dict[str, Any]]:
        """List all configured cameras."""
        with self._lock:
            return [
                {
                    "name": slot.name,
                    "type": slot.config.camera_type,
                    "enabled": slot.enabled,
                    "last_capture": slot.last_capture_path,
                }
                for slot in self._cameras.values()
            ]

    def get_camera_count(self) -> int:
        """Number of configured cameras."""
        return len(self._cameras)

    def get_enabled_count(self) -> int:
        """Number of enabled cameras."""
        with self._lock:
            return sum(1 for s in self._cameras.values() if s.enabled)


__all__ = ["MultiCameraManager", "CameraSlot"]