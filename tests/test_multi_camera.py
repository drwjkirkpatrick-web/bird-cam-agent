"""tests/test_multi_camera.py — Multi-camera tests."""

import pytest

from core.types import CameraConfig
from modules.multi_camera import MultiCameraManager


@pytest.fixture
def manager():
    return MultiCameraManager()


class TestAddRemove:
    def test_add_camera(self, manager):
        manager.add_camera("front", CameraConfig(mock_mode=True))
        assert manager.get_camera_count() == 1

    def test_remove_camera(self, manager):
        manager.add_camera("front", CameraConfig(mock_mode=True))
        assert manager.remove_camera("front") is True
        assert manager.get_camera_count() == 0

    def test_remove_nonexistent(self, manager):
        assert manager.remove_camera("nonexistent") is False


class TestEnableDisable:
    def test_disable_camera(self, manager):
        manager.add_camera("front", CameraConfig(mock_mode=True))
        manager.disable_camera("front")
        assert manager.get_enabled_count() == 0

    def test_enable_camera(self, manager):
        manager.add_camera("front", CameraConfig(mock_mode=True))
        manager.disable_camera("front")
        manager.enable_camera("front")
        assert manager.get_enabled_count() == 1


class TestCapture:
    def test_capture_all_mock(self, manager):
        manager.add_camera("front", CameraConfig(mock_mode=True))
        manager.add_camera("side", CameraConfig(mock_mode=True))
        results = manager.capture_all()
        assert len(results) == 2
        assert "front" in results
        assert "side" in results

    def test_capture_one(self, manager):
        manager.add_camera("front", CameraConfig(mock_mode=True))
        result = manager.capture_one("front")
        assert result is not None

    def test_capture_nonexistent(self, manager):
        assert manager.capture_one("nonexistent") is None

    def test_capture_disabled(self, manager):
        manager.add_camera("front", CameraConfig(mock_mode=True))
        manager.disable_camera("front")
        assert manager.capture_one("front") is None


class TestList:
    def test_list_cameras(self, manager):
        manager.add_camera("front", CameraConfig(mock_mode=True))
        manager.add_camera("side", CameraConfig(mock_mode=True))
        cams = manager.list_cameras()
        assert len(cams) == 2
        assert cams[0]["name"] == "front"
