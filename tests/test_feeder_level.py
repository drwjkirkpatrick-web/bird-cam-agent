"""tests/test_feeder_level.py"""

import pytest
from modules.feeder_level import FeederLevelMonitor

@pytest.fixture
def monitor():
    return FeederLevelMonitor({"mock_mode": True})

class TestFeederLevel:
    def test_get_level(self, monitor):
        level = monitor.get_level()
        assert 0 <= level <= 100
    def test_is_low(self, monitor):
        monitor._mock_level = 15.0
        assert monitor.is_low() is True
    def test_not_low(self, monitor):
        monitor._mock_level = 80.0
        assert monitor.is_low() is False
    def test_should_alert(self, monitor):
        monitor._mock_level = 15.0
        assert monitor.should_send_alert() is True
    def test_no_duplicate_alert(self, monitor):
        monitor._mock_level = 15.0
        monitor.should_send_alert()
        assert monitor.should_send_alert() is False
    def test_status(self, monitor):
        s = monitor.get_status()
        assert "level_pct" in s
        assert "status" in s
