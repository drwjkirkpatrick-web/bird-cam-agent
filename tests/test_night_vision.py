"""tests/test_night_vision.py — Night vision controller tests."""

import os
import tempfile

import pytest

from modules.night_vision import (
    NightVisionController,
    NightVisionConfig,
    CaptureMode,
)


@pytest.fixture
def controller():
    return NightVisionController(NightVisionConfig(mock_mode=True))


class TestCaptureMode:
    def test_day_mode(self):
        assert CaptureMode.from_brightness(0.8) == CaptureMode.DAY

    def test_dusk_mode(self):
        assert CaptureMode.from_brightness(0.3) == CaptureMode.DUSK

    def test_night_mode(self):
        assert CaptureMode.from_brightness(0.01) == CaptureMode.NIGHT

    def test_dawn_mode(self):
        assert CaptureMode.from_brightness(0.08) == CaptureMode.DAWN


class TestBrightness:
    def test_mock_brightness_returns_float(self, controller):
        b = controller.measure_brightness("nonexistent.jpg")
        assert isinstance(b, float)
        assert 0.0 <= b <= 1.0

    def test_missing_photo_returns_value(self, controller):
        b = controller.measure_brightness("/nonexistent/path.jpg")
        assert 0.0 <= b <= 1.0


class TestCaptureModeWithHysteresis:
    def test_starts_in_day_mode(self, controller):
        assert controller.current_mode == CaptureMode.DAY

    def test_transitions_to_dusk(self, controller):
        controller.get_capture_mode(0.3)
        assert controller.current_mode == CaptureMode.DUSK

    def test_transitions_to_night(self, controller):
        controller.get_capture_mode(0.3)  # dusk
        controller.get_capture_mode(0.01)  # night
        assert controller.current_mode == CaptureMode.NIGHT

    def test_hysteresis_prevents_flicker(self, controller):
        # Go to night mode
        controller.get_capture_mode(0.01)
        assert controller.current_mode == CaptureMode.NIGHT
        # Small brightness increase shouldn't leave night mode immediately
        controller.get_capture_mode(0.06)  # just above dawn threshold
        # With hysteresis, should stay in NIGHT or go to DAWN
        assert controller.current_mode in (CaptureMode.NIGHT, CaptureMode.DAWN)


class TestCameraSettings:
    def test_day_settings(self, controller):
        settings = controller.get_camera_settings(CaptureMode.DAY)
        assert settings["iso"] == 100
        assert settings["white_balance"] == "auto"

    def test_night_settings(self, controller):
        settings = controller.get_camera_settings(CaptureMode.NIGHT)
        assert settings["iso"] == 800
        assert settings["exposure_ms"] == 10.0

    def test_dusk_settings(self, controller):
        settings = controller.get_camera_settings(CaptureMode.DUSK)
        assert settings["iso"] == 400

    def test_dawn_settings(self, controller):
        settings = controller.get_camera_settings(CaptureMode.DAWN)
        assert settings["iso"] == 400

    def test_night_settings_have_reduced_saturation(self, controller):
        day = controller.get_camera_settings(CaptureMode.DAY)
        night = controller.get_camera_settings(CaptureMode.NIGHT)
        assert night["saturation"] < day["saturation"]


class TestIRIlluminator:
    def test_ir_off_by_default(self, controller):
        assert controller.ir_on is False

    def test_ir_on(self, controller):
        controller.set_ir_illuminator(True)
        assert controller.ir_on is True

    def test_ir_off(self, controller):
        controller.set_ir_illuminator(True)
        controller.set_ir_illuminator(False)
        assert controller.ir_on is False

    def test_cleanup_turns_off_ir(self, controller):
        controller.set_ir_illuminator(True)
        controller.cleanup()
        assert controller.ir_on is False


class TestBrightnessHistory:
    def test_history_starts_empty(self, controller):
        assert len(controller.get_brightness_history()) == 0

    def test_history_grows_with_measurements(self, controller):
        controller.get_capture_mode(0.5)
        controller.get_capture_mode(0.3)
        controller.get_capture_mode(0.1)
        assert len(controller.get_brightness_history()) == 3

    def test_history_capped(self, controller):
        for i in range(15):
            controller.get_capture_mode(0.5)
        assert len(controller.get_brightness_history()) <= 10


class TestLightTrend:
    def test_stable_with_few_readings(self, controller):
        assert controller.get_light_trend() == "stable"

    def test_increasing(self, controller):
        controller.get_capture_mode(0.1)
        controller.get_capture_mode(0.3)
        controller.get_capture_mode(0.6)
        assert controller.get_light_trend() == "increasing"

    def test_decreasing(self, controller):
        controller.get_capture_mode(0.6)
        controller.get_capture_mode(0.3)
        controller.get_capture_mode(0.1)
        assert controller.get_light_trend() == "decreasing"

    def test_stable(self, controller):
        controller.get_capture_mode(0.5)
        controller.get_capture_mode(0.5)
        controller.get_capture_mode(0.5)
        assert controller.get_light_trend() == "stable"