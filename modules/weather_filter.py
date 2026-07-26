"""
modules/weather_filter.py — Weather-based capture filtering.

NOTE: Adjusts capture behavior based on weather conditions. Heavy rain,
      extreme heat, or high wind can reduce bird activity and photo quality.
      This module helps the orchestrator decide when to capture more or less
      frequently.

WHY: Bird activity varies dramatically with weather. A smart bird cam should
     capture more during active weather (clear, mild) and less during
     suboptimal conditions (heavy rain, extreme heat) to save power and
     storage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class WeatherCondition(Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    HEAVY_RAIN = "heavy_rain"
    SNOW = "snow"
    FOG = "fog"
    HIGH_WIND = "high_wind"
    EXTREME_HEAT = "extreme_heat"
    EXTREME_COLD = "extreme_cold"
    UNKNOWN = "unknown"


@dataclass
class WeatherData:
    """Current weather conditions."""
    condition: WeatherCondition = WeatherCondition.UNKNOWN
    temperature_c: float = 20.0
    humidity_pct: float = 50.0
    wind_kph: float = 5.0
    visibility_km: float = 10.0
    is_daytime: bool = True
    source: str = "mock"


class WeatherFilter:
    """
    Filters and adjusts capture behavior based on weather.

    Usage:
        weather = WeatherFilter()
        weather.update(WeatherData(condition=WeatherCondition.CLEAR))
        if weather.should_capture():
            agent.run_single_capture()
        interval = weather.get_adjusted_interval(base_interval=30)
    """

    # NOTE: Bird activity factors by weather condition (0.0-1.0)
    ACTIVITY_FACTORS: dict[WeatherCondition, float] = {
        WeatherCondition.CLEAR: 1.0,
        WeatherCondition.CLOUDY: 0.8,
        WeatherCondition.RAIN: 0.4,
        WeatherCondition.HEAVY_RAIN: 0.1,
        WeatherCondition.SNOW: 0.3,
        WeatherCondition.FOG: 0.5,
        WeatherCondition.HIGH_WIND: 0.3,
        WeatherCondition.EXTREME_HEAT: 0.2,
        WeatherCondition.EXTREME_COLD: 0.3,
        WeatherCondition.UNKNOWN: 0.7,
    }

    def __init__(self):
        self._current_weather: WeatherData = WeatherData()

    def update(self, weather: WeatherData) -> None:
        """Update current weather conditions."""
        self._current_weather = weather
        logger.info("Weather updated: %s, %.1f°C, wind %.1f kph",
                     weather.condition.value, weather.temperature_c, weather.wind_kph)

    def should_capture(self) -> bool:
        """Decide if a capture should happen now based on weather."""
        condition = self._current_weather.condition
        factor = self.ACTIVITY_FACTORS.get(condition, 0.7)
        # NOTE: Don't capture in heavy rain or extreme conditions
        if condition in (WeatherCondition.HEAVY_RAIN,):
            return False
        if factor < 0.15:
            return False
        return True

    def get_adjusted_interval(self, base_interval: float) -> float:
        """
        Adjust capture interval based on weather.

        Good weather → shorter interval (more captures).
        Bad weather → longer interval (fewer captures, save power).
        """
        factor = self.ACTIVITY_FACTORS.get(self._current_weather.condition, 0.7)
        # NOTE: Inverse relationship — high activity factor = short interval
        if factor <= 0:
            return base_interval * 10  # Very long interval
        adjusted = base_interval / factor
        # Clamp to reasonable range
        return max(base_interval * 0.5, min(adjusted, base_interval * 5))

    def get_activity_factor(self) -> float:
        """Return the current bird activity factor (0.0-1.0)."""
        return self.ACTIVITY_FACTORS.get(self._current_weather.condition, 0.7)

    def get_capture_priority(self) -> str:
        """Return priority level for current weather."""
        factor = self.get_activity_factor()
        if factor >= 0.8:
            return "high"
        elif factor >= 0.5:
            return "medium"
        elif factor >= 0.2:
            return "low"
        return "minimal"

    def get_weather_summary(self) -> dict[str, Any]:
        """Return a summary of current weather and its impact."""
        return {
            "condition": self._current_weather.condition.value,
            "temperature_c": self._current_weather.temperature_c,
            "humidity_pct": self._current_weather.humidity_pct,
            "wind_kph": self._current_weather.wind_kph,
            "activity_factor": self.get_activity_factor(),
            "capture_priority": self.get_capture_priority(),
            "should_capture": self.should_capture(),
            "adjusted_interval": self.get_adjusted_interval(30.0),
        }

    @property
    def current_weather(self) -> WeatherData:
        return self._current_weather


__all__ = ["WeatherFilter", "WeatherData", "WeatherCondition"]