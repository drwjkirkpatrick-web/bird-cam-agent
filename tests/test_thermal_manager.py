"""tests/test_thermal_manager.py"""

import pytest
from modules.thermal_manager import ThermalManager

@pytest.fixture
def manager():
    return ThermalManager({"mock_mode": True})

class TestThermal:
    def test_get_temperature(self, manager):
        temp = manager.get_temperature()
        assert isinstance(temp, float)
        assert temp > 0
    def test_should_activate_cooling(self, manager):
        manager._mock_temp = 70.0
        assert manager.should_activate_cooling() is True
    def test_should_not_activate_cooling(self, manager):
        manager._mock_temp = 40.0
        assert manager.should_activate_cooling() is False
    def test_is_critical(self, manager):
        manager._mock_temp = 85.0
        assert manager.is_critical() is True
    def test_activate_cooling(self, manager):
        assert manager.activate_cooling() is True
        assert manager.fan_active is True
    def test_deactivate_cooling(self, manager):
        manager.activate_cooling()
        assert manager.deactivate_cooling() is True
        assert manager.fan_active is False
    def test_auto_manage(self, manager):
        manager._mock_temp = 70.0
        status = manager.auto_manage()
        assert status["fan_active"] is True
    def test_get_status(self, manager):
        s = manager.get_status()
        assert "temperature_c" in s
        assert "status" in s
    def test_cleanup(self, manager):
        manager.activate_cooling()
        manager.cleanup()
        assert manager.fan_active is False
