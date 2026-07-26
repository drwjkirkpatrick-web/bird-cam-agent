"""tests/test_weather_filter.py — Weather filter tests."""

import pytest

from modules.weather_filter import WeatherFilter, WeatherData, WeatherCondition


@pytest.fixture
def filter_obj():
    return WeatherFilter()


class TestShouldCapture:
    def test_clear_weather(self, filter_obj):
        filter_obj.update(WeatherData(condition=WeatherCondition.CLEAR))
        assert filter_obj.should_capture() is True

    def test_heavy_rain(self, filter_obj):
        filter_obj.update(WeatherData(condition=WeatherCondition.HEAVY_RAIN))
        assert filter_obj.should_capture() is False

    def test_unknown_weather(self, filter_obj):
        filter_obj.update(WeatherData(condition=WeatherCondition.UNKNOWN))
        assert filter_obj.should_capture() is True


class TestAdjustedInterval:
    def test_clear_shorter_interval(self, filter_obj):
        filter_obj.update(WeatherData(condition=WeatherCondition.CLEAR))
        interval = filter_obj.get_adjusted_interval(30.0)
        assert interval <= 30.0

    def test_rain_longer_interval(self, filter_obj):
        filter_obj.update(WeatherData(condition=WeatherCondition.RAIN))
        interval = filter_obj.get_adjusted_interval(30.0)
        assert interval > 30.0


class TestActivityFactor:
    def test_clear_factor(self, filter_obj):
        filter_obj.update(WeatherData(condition=WeatherCondition.CLEAR))
        assert filter_obj.get_activity_factor() == 1.0

    def test_rain_factor(self, filter_obj):
        filter_obj.update(WeatherData(condition=WeatherCondition.RAIN))
        assert filter_obj.get_activity_factor() == 0.4


class TestPriority:
    def test_high_priority(self, filter_obj):
        filter_obj.update(WeatherData(condition=WeatherCondition.CLEAR))
        assert filter_obj.get_capture_priority() == "high"

    def test_low_priority(self, filter_obj):
        filter_obj.update(WeatherData(condition=WeatherCondition.RAIN))
        assert filter_obj.get_capture_priority() == "low"


class TestSummary:
    def test_summary_structure(self, filter_obj):
        filter_obj.update(WeatherData(condition=WeatherCondition.CLEAR, temperature_c=22.0))
        summary = filter_obj.get_weather_summary()
        assert "condition" in summary
        assert "activity_factor" in summary
        assert "should_capture" in summary
