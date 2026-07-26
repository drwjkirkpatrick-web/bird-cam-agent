"""tests/test_environmental_sensor.py"""

import pytest
from modules.environmental_sensor import EnvironmentalSensor, EnvironmentalReading

@pytest.fixture
def sensor():
    return EnvironmentalSensor({"mock_mode": True})

class TestSensor:
    def test_read(self, sensor):
        reading = sensor.read()
        assert isinstance(reading, EnvironmentalReading)
        assert reading.temperature_c > -50
        assert reading.temperature_c < 60
    def test_humidity_range(self, sensor):
        reading = sensor.read()
        assert 0 <= reading.humidity_pct <= 100
    def test_summary(self, sensor):
        s = sensor.get_summary()
        assert "temperature_c" in s
        assert "humidity_pct" in s
        assert "pressure_hpa" in s
    def test_dew_point(self, sensor):
        reading = sensor.read()
        assert reading.dew_point_c <= reading.temperature_c
