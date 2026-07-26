"""tests/test_power_monitor.py"""

import pytest
from modules.power_monitor import PowerMonitor, PowerStatus

@pytest.fixture
def monitor():
    return PowerMonitor({"mock_mode": True})

class TestPower:
    def test_get_status(self, monitor):
        status = monitor.get_status()
        assert isinstance(status, PowerStatus)
        assert 0 <= status.battery_pct <= 100
    def test_low_battery(self, monitor):
        monitor._mock_battery = 15.0
        assert monitor.is_low_battery() is True
    def test_not_low_battery(self, monitor):
        monitor._mock_battery = 80.0
        assert monitor.is_low_battery() is False
    def test_critical_battery(self, monitor):
        monitor._mock_battery = 5.0
        assert monitor.is_critical_battery() is True
    def test_should_send_alert(self, monitor):
        monitor._mock_battery = 15.0
        assert monitor.should_send_alert() is True
    def test_no_duplicate_alert(self, monitor):
        monitor._mock_battery = 15.0
        monitor.should_send_alert()
        assert monitor.should_send_alert() is False
    def test_power_summary(self, monitor):
        s = monitor.get_power_summary()
        assert "battery_pct" in s
        assert "source" in s
