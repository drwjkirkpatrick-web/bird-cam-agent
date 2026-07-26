"""
modules/night_vision.py — Low-light and night capture mode.

NOTE: This module enhances the bird cam for low-light and nighttime
      operation. It detects ambient light levels and adjusts camera
      settings accordingly, supports IR illuminator control, and can
      switch between day and night capture modes.

WHY: Many interesting birds visit feeders at dawn, dusk, and night
     (owls, nightjars, nighthawks). The standard camera settings that
     work in daylight produce dark, noisy images at night. This module
     adapts capture parameters based on available light.

FEATURES:
  - Light level detection (from photo brightness or external sensor)
  - Automatic ISO/gain adjustment for low light
  - IR illuminator on/off control (via GPIO pin)
  - Day/night mode switching with hysteresis (prevents flicker)
  - Exposure compensation for dawn/dusk transitions
  - Mock mode for development without hardware
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CaptureMode(Enum):
    """Camera capture mode based on ambient light."""
    DAY = "day"
    DUSK = "dusk"
    NIGHT = "night"
    DAWN = "dawn"

    @classmethod
    def from_brightness(cls, brightness: float) -> "CaptureMode":
        """
        Determine capture mode from brightness level (0.0-1.0).

        NOTE: Hysteresis thresholds prevent rapid mode switching when
              brightness is near a boundary. The hysteresis gap is 0.1.
        """
        if brightness >= 0.5:
            return cls.DAY
        elif brightness >= 0.2:
            return cls.DUSK
        elif brightness >= 0.05:
            return cls.DAWN
        else:
            return cls.NIGHT


@dataclass
class NightVisionConfig:
    """Configuration for night vision module."""
    ir_gpio_pin: int = 18  # GPIO pin for IR illuminator relay
    ir_enabled: bool = False
    light_sensor_pin: int | None = None  # Optional analog light sensor
    day_iso: int = 100
    dusk_iso: int = 400
    night_iso: int = 800
    day_exposure: float = 1.0  # ms
    night_exposure: float = 10.0  # ms
    night_white_balance: str = "auto"  # auto, daylight, cloudy, tungsten
    hysteresis_gap: float = 0.1
    mock_mode: bool = True
    brightness_threshold_day: float = 0.5
    brightness_threshold_dusk: float = 0.2
    brightness_threshold_dawn: float = 0.05


class NightVisionController:
    """
    Controls camera settings and IR illuminator based on ambient light.

    Usage:
        controller = NightVisionController(config)
        brightness = controller.measure_brightness("photo.jpg")
        mode = controller.get_capture_mode(brightness)
        settings = controller.get_camera_settings(mode)
        controller.set_ir_illuminator(mode == CaptureMode.NIGHT)
    """

    def __init__(self, config: NightVisionConfig | None = None):
        self.config = config or NightVisionConfig()
        self._current_mode: CaptureMode = CaptureMode.DAY
        self._ir_on = False
        self._brightness_history: list[float] = []
        self._max_history = 10

    def measure_brightness(self, photo_path: str) -> float:
        """
        Measure average brightness of a photo (0.0 = black, 1.0 = white).

        NOTE: Uses PIL if available, otherwise returns a mock value.
        """
        if self.config.mock_mode:
            # NOTE: In mock mode, return a simulated brightness based on time of day
            return self._mock_brightness()

        if not os.path.exists(photo_path):
            logger.warning("Photo not found for brightness measurement: %s", photo_path)
            return 0.5

        try:
            from PIL import Image

            img = Image.open(photo_path).convert("L")  # Convert to grayscale
            # NOTE: Sample a small region for speed (center 100x100)
            w, h = img.size
            crop = img.crop((w // 2 - 50, h // 2 - 50, w // 2 + 50, h // 2 + 50))
            pixels = list(crop.getdata())
            avg = sum(pixels) / len(pixels) / 255.0
            return avg
        except ImportError:
            logger.warning("PIL not available — using mock brightness")
            return self._mock_brightness()
        except Exception as e:
            logger.error("Brightness measurement failed: %s", e)
            return 0.5

    def get_capture_mode(self, brightness: float) -> CaptureMode:
        """
        Determine the capture mode from brightness, with hysteresis.

        NOTE: Hysteresis prevents rapid mode switching when brightness
              hovers near a threshold. Once we switch to NIGHT, we don't
              switch back to DAWN until brightness rises above the
              threshold + hysteresis_gap.
        """
        # Apply hysteresis based on current mode
        gap = self.config.hysteresis_gap

        if self._current_mode == CaptureMode.NIGHT:
            # Need brightness above dawn_threshold + gap to leave night mode
            if brightness >= self.config.brightness_threshold_dawn + gap:
                mode = CaptureMode.from_brightness(brightness)
            else:
                mode = CaptureMode.NIGHT
        elif self._current_mode == CaptureMode.DAWN:
            if brightness >= self.config.brightness_threshold_dusk + gap:
                mode = CaptureMode.from_brightness(brightness)
            elif brightness < self.config.brightness_threshold_dawn:
                mode = CaptureMode.NIGHT
            else:
                mode = CaptureMode.DAWN
        elif self._current_mode == CaptureMode.DUSK:
            if brightness >= self.config.brightness_threshold_day + gap:
                mode = CaptureMode.DAY
            elif brightness < self.config.brightness_threshold_dusk:
                mode = CaptureMode.from_brightness(brightness)
            else:
                mode = CaptureMode.DUSK
        else:  # DAY
            if brightness < self.config.brightness_threshold_day - gap:
                mode = CaptureMode.from_brightness(brightness)
            else:
                mode = CaptureMode.DAY

        self._current_mode = mode
        self._add_to_history(brightness)
        return mode

    def get_camera_settings(self, mode: CaptureMode) -> dict[str, Any]:
        """
        Get camera settings optimized for the given capture mode.

        Returns a dict of camera parameters (ISO, exposure, white balance, etc.)
        """
        settings = {
            CaptureMode.DAY: {
                "iso": self.config.day_iso,
                "exposure_ms": self.config.day_exposure,
                "white_balance": "auto",
                "awb_gains": (1.5, 1.5),
                "brightness": 50,  # 0-100
                "contrast": 0,
                "saturation": 0,
                "sharpness": 0,
            },
            CaptureMode.DUSK: {
                "iso": self.config.dusk_iso,
                "exposure_ms": self.config.day_exposure * 2,
                "white_balance": "auto",
                "awb_gains": (2.0, 1.8),
                "brightness": 55,
                "contrast": 5,
                "saturation": -10,  # Reduce saturation in warm dusk light
                "sharpness": 0,
            },
            CaptureMode.NIGHT: {
                "iso": self.config.night_iso,
                "exposure_ms": self.config.night_exposure,
                "white_balance": self.config.night_white_balance,
                "awb_gains": (3.0, 2.5),
                "brightness": 60,
                "contrast": 10,
                "saturation": -20,  # Night images are mostly monochrome anyway
                "sharpness": -10,  # Reduce sharpening to avoid amplifying noise
            },
            CaptureMode.DAWN: {
                "iso": self.config.dusk_iso,
                "exposure_ms": self.config.day_exposure * 1.5,
                "white_balance": "auto",
                "awb_gains": (2.5, 2.0),
                "brightness": 55,
                "contrast": 5,
                "saturation": -5,
                "sharpness": 0,
            },
        }
        return settings.get(mode, settings[CaptureMode.DAY])

    def set_ir_illuminator(self, on: bool) -> bool:
        """
        Turn the IR illuminator on or off via GPIO.

        NOTE: In mock mode, just logs the action. On real hardware,
              this toggles a GPIO pin connected to an IR LED relay.
        """
        if self.config.mock_mode:
            logger.info("[MOCK] IR illuminator %s", "ON" if on else "OFF")
            self._ir_on = on
            return True

        try:
            import RPi.GPIO as GPIO

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.config.ir_gpio_pin, GPIO.OUT)
            GPIO.output(self.config.ir_gpio_pin, GPIO.HIGH if on else GPIO.LOW)
            self._ir_on = on
            logger.info("IR illuminator %s (GPIO %d)", "ON" if on else "OFF", self.config.ir_gpio_pin)
            return True
        except ImportError:
            logger.warning("RPi.GPIO not available — IR control skipped")
            self._ir_on = on  # Track state even without hardware
            return True
        except Exception as e:
            logger.error("IR illuminator control failed: %s", e)
            return False

    @property
    def ir_on(self) -> bool:
        """Whether the IR illuminator is currently on."""
        return self._ir_on

    @property
    def current_mode(self) -> CaptureMode:
        """Current capture mode."""
        return self._current_mode

    def get_brightness_history(self) -> list[float]:
        """Return recent brightness readings."""
        return list(self._brightness_history)

    def get_light_trend(self) -> str:
        """
        Determine if light is increasing, decreasing, or stable.

        Returns 'increasing', 'decreasing', or 'stable'.
        """
        if len(self._brightness_history) < 3:
            return "stable"

        recent = self._brightness_history[-3:]
        avg_first = (recent[0] + recent[1]) / 2
        avg_last = (recent[1] + recent[2]) / 2
        diff = avg_last - avg_first

        if diff > 0.02:
            return "increasing"
        elif diff < -0.02:
            return "decreasing"
        return "stable"

    def _mock_brightness(self) -> float:
        """Simulate brightness based on time of day for mock mode."""
        hour = time.localtime().tm_hour
        if 6 <= hour <= 18:
            # Daytime: high brightness with slight variation
            return 0.7 + 0.1 * (1 - abs(hour - 12) / 6)
        elif 5 <= hour < 6 or 18 < hour <= 20:
            # Dawn/dusk transition
            return 0.2
        else:
            # Night
            return 0.02

    def _add_to_history(self, brightness: float) -> None:
        """Add a brightness reading to the history (capped)."""
        self._brightness_history.append(brightness)
        if len(self._brightness_history) > self._max_history:
            self._brightness_history = self._brightness_history[-self._max_history:]

    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        if not self.config.mock_mode:
            try:
                import RPi.GPIO as GPIO

                GPIO.output(self.config.ir_gpio_pin, GPIO.LOW)
                GPIO.cleanup(self.config.ir_gpio_pin)
            except Exception:
                pass
        self._ir_on = False


__all__ = ["NightVisionController", "NightVisionConfig", "CaptureMode"]