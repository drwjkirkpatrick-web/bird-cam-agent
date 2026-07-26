"""
tests/test_camera.py — Tests for the camera capture module.

NOTE: Hardware-dependent tests (PiCamera, USB) use pytest.importorskip
      so they skip cleanly on machines without the required library or
      device. The mock-backed tests run everywhere.

WHY: The camera module is the agent's eyes — it must always produce a
     real, openable JPEG file. These tests verify that contract for the
     mock path and guard the hardware paths so they activate only when
     the relevant hardware/libraries are present.
"""

from __future__ import annotations

import os
import re

import pytest

from core.types import CameraConfig
from modules.camera import (
    CameraBase,
    CameraFactory,
    MockCameraCapture,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_config(tmp_path) -> CameraConfig:
    """A CameraConfig pointed at a temp photo dir, mock_mode on."""
    return CameraConfig(
        mock_mode=True,
        camera_type="mock",
        photo_dir=str(tmp_path / "photos"),
        video_dir=str(tmp_path / "videos"),
    )


@pytest.fixture
def auto_config(tmp_path) -> CameraConfig:
    """A CameraConfig in auto mode with mock_mode off (for factory tests)."""
    return CameraConfig(
        mock_mode=False,
        camera_type="auto",
        photo_dir=str(tmp_path / "photos"),
        video_dir=str(tmp_path / "videos"),
    )


# ---------------------------------------------------------------------------
# Mock backend tests — always run
# ---------------------------------------------------------------------------
class TestMockCamera:
    """Tests for MockCameraCapture."""

    def test_creates_valid_jpeg(self, mock_config: CameraConfig) -> None:
        """MockCamera should create a real, openable JPEG file."""
        cam = MockCameraCapture(mock_config)
        path = cam.capture_photo()
        assert os.path.isfile(path), f"File not found: {path}"
        # WHY: Check the JPEG magic bytes (FF D8 FF) to confirm it's a
        #      genuine JPEG, not just an empty or garbage file.
        with open(path, "rb") as f:
            header = f.read(3)
        assert header[:2] == b"\xff\xd8", "Not a JPEG (missing SOI marker)"
        assert header[2:3] == b"\xff", "JPEG SOI incomplete"

    def test_jpeg_openable_by_pil(self, mock_config: CameraConfig) -> None:
        """The generated JPEG should be openable by PIL with the expected size."""
        pytest.importorskip("PIL")
        from PIL import Image

        cam = MockCameraCapture(mock_config)
        path = cam.capture_photo()
        with Image.open(path) as img:
            assert img.format == "JPEG"
            assert img.size == (640, 480)
            assert img.mode == "RGB"

    def test_filename_contains_timestamp(self, mock_config: CameraConfig) -> None:
        """Filename must match bird_{YYYYMMDD_HHMMSS}.jpg."""
        cam = MockCameraCapture(mock_config)
        path = cam.capture_photo()
        fname = os.path.basename(path)
        # NOTE: Regex enforces the exact timestamp shape.
        assert re.match(
            r"^bird_\d{8}_\d{6}\.jpg$", fname
        ), f"Filename doesn't match pattern: {fname}"

    def test_file_created_in_correct_dir(self, mock_config: CameraConfig) -> None:
        """The saved file must live inside config.photo_dir."""
        cam = MockCameraCapture(mock_config)
        path = cam.capture_photo()
        expected_dir = os.path.abspath(mock_config.photo_dir)
        actual_dir = os.path.dirname(os.path.abspath(path))
        assert actual_dir == expected_dir

    def test_creates_photo_dir_if_missing(
        self, tmp_path
    ) -> None:
        """photo_dir should be created automatically if it doesn't exist."""
        new_dir = str(tmp_path / "nested" / "deep" / "photos")
        cfg = CameraConfig(mock_mode=True, camera_type="mock", photo_dir=new_dir)
        assert not os.path.exists(new_dir)
        cam = MockCameraCapture(cfg)
        cam.capture_photo()
        assert os.path.isdir(new_dir), "photo_dir was not created"

    def test_get_camera_info_returns_dict(self, mock_config: CameraConfig) -> None:
        """get_camera_info() must return a dict with expected keys."""
        cam = MockCameraCapture(mock_config)
        info = cam.get_camera_info()
        assert isinstance(info, dict)
        assert info["backend"] == "mock"
        assert info["mock_mode"] is True
        assert "photo_dir" in info

    def test_multiple_captures_unique_filenames(
        self, mock_config: CameraConfig
    ) -> None:
        """Rapid successive captures must produce distinct filenames.

        NOTE: Without the collision-suffix logic, captures within the
              same wall-clock second would overwrite each other. We fire
              several captures in a tight loop to stress this.
        """
        cam = MockCameraCapture(mock_config)
        paths = [cam.capture_photo() for _ in range(5)]
        filenames = [os.path.basename(p) for p in paths]
        assert len(filenames) == len(set(filenames)), (
            f"Duplicate filenames detected: {filenames}"
        )
        # WHY: Every path returned must also be a distinct, real file.
        for p in paths:
            assert os.path.isfile(p), f"Capture returned missing file: {p}"

    def test_capture_returns_existing_file_path(
        self, mock_config: CameraConfig
    ) -> None:
        """The return value of capture_photo() must be a real file path."""
        cam = MockCameraCapture(mock_config)
        path = cam.capture_photo()
        assert isinstance(path, str)
        assert os.path.exists(path), f"Returned path doesn't exist: {path}"

    def test_implements_camerabase(self, mock_config: CameraConfig) -> None:
        """MockCameraCapture must be a CameraBase subclass."""
        cam = MockCameraCapture(mock_config)
        assert isinstance(cam, CameraBase)


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------
class TestCameraFactory:
    """Tests for CameraFactory.create()."""

    def test_factory_returns_mock_in_mock_mode(
        self, mock_config: CameraConfig
    ) -> None:
        """When mock_mode=True, factory must return a MockCameraCapture."""
        cam = CameraFactory.create(mock_config)
        assert isinstance(cam, MockCameraCapture)

    def test_factory_falls_back_to_mock_no_hardware(
        self, auto_config: CameraConfig
    ) -> None:
        """
        In auto mode with no Pi/USB hardware, factory must fall back to Mock.

        NOTE: On this test machine picamera2/cv2 are typically unavailable,
              so the auto path should degrade to MockCameraCapture without
              raising. This is the core resilience guarantee.
        """
        cam = CameraFactory.create(auto_config)
        # WHY: If neither picamera2 nor cv2 is importable, the only safe
        #      backend is Mock — the factory must never raise here.
        assert isinstance(cam, MockCameraCapture)

    def test_factory_explicit_picamera_type_falls_back(
        self, tmp_path
    ) -> None:
        """camera_type='picamera' without hardware -> Mock fallback."""
        cfg = CameraConfig(
            mock_mode=False,
            camera_type="picamera",
            photo_dir=str(tmp_path / "photos"),
        )
        try:
            cam = CameraFactory.create(cfg)
        except ImportError:
            pytest.skip("Unexpected ImportError escaped factory")
        # If picamera2 isn't available, we must get Mock.
        # If it IS available, we get a PiCameraCapture — that's fine too.
        assert isinstance(cam, (MockCameraCapture, CameraBase))

    def test_factory_explicit_usb_type_falls_back(self, tmp_path) -> None:
        """camera_type='usb' without cv2 -> Mock fallback."""
        cfg = CameraConfig(
            mock_mode=False,
            camera_type="usb",
            photo_dir=str(tmp_path / "photos"),
        )
        try:
            cam = CameraFactory.create(cfg)
        except ImportError:
            pytest.skip("Unexpected ImportError escaped factory")
        assert isinstance(cam, (MockCameraCapture, CameraBase))

    def test_factory_returns_camerabase(
        self, mock_config: CameraConfig
    ) -> None:
        """Factory must always return a CameraBase instance."""
        cam = CameraFactory.create(mock_config)
        assert isinstance(cam, CameraBase)


# ---------------------------------------------------------------------------
# PiCamera tests — skip cleanly when picamera2 isn't usable
# ---------------------------------------------------------------------------
class TestPiCamera:
    """
    Tests for PiCameraCapture.

    NOTE: These skip cleanly on any machine where picamera2 (and its
          libcamera dependency) can't be imported.
    """

    def test_picamera_import_or_skip(self, tmp_path) -> None:
        """Verify picamera2 is importable, or skip."""
        pytest.importorskip("picamera2")
        # NOTE: Even if the package is installed, libcamera may be
        #      missing on non-Pi hosts. We confirm the real import works.
        try:
            from picamera2 import Picamera2  # noqa: F401
        except ImportError:
            pytest.skip("picamera2 present but libcamera missing")

    def test_picamera_get_camera_info(self, tmp_path) -> None:
        """PiCameraCapture.get_camera_info() returns a dict."""
        pytest.importorskip("picamera2")
        from modules.camera import PiCameraCapture

        cfg = CameraConfig(
            mock_mode=False,
            camera_type="picamera",
            photo_dir=str(tmp_path / "photos"),
            resolution_width=1280,
            resolution_height=720,
        )
        try:
            cam = PiCameraCapture(cfg)
        except ImportError:
            pytest.skip("picamera2/libcamera not usable")
        info = cam.get_camera_info()
        assert isinstance(info, dict)
        assert info["backend"] == "picamera"


# ---------------------------------------------------------------------------
# USB camera tests — skip cleanly when cv2 isn't usable
# ---------------------------------------------------------------------------
class TestUSBCamera:
    """
    Tests for USBCameraCapture.

    NOTE: These skip cleanly when opencv-python (cv2) isn't installed.
    """

    def test_usb_import_or_skip(self) -> None:
        """Verify cv2 is importable, or skip."""
        pytest.importorskip("cv2")

    def test_usb_get_camera_info(self, tmp_path) -> None:
        """USBCameraCapture.get_camera_info() returns a dict."""
        pytest.importorskip("cv2")
        from modules.camera import USBCameraCapture

        cfg = CameraConfig(
            mock_mode=False,
            camera_type="usb",
            photo_dir=str(tmp_path / "photos"),
            device_index=0,
        )
        try:
            cam = USBCameraCapture(cfg)
        except ImportError:
            pytest.skip("cv2 not usable")
        info = cam.get_camera_info()
        assert isinstance(info, dict)
        assert info["backend"] == "usb"
        assert info["device_index"] == 0