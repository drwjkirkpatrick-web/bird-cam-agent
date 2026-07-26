"""tests/test_system_health.py"""

import pytest
from modules.system_health import SystemHealthMonitor

@pytest.fixture
def monitor():
    return SystemHealthMonitor({"mock_mode": True})

class TestHealth:
    def test_get_cpu_temp(self, monitor):
        temp = monitor.get_cpu_temp()
        assert isinstance(temp, float)
        assert temp > 0
    def test_disk_usage(self, monitor):
        disk = monitor.get_disk_usage()
        assert "used_pct" in disk
        assert "total_gb" in disk
    def test_memory_usage(self, monitor):
        mem = monitor.get_memory_usage()
        assert "used_pct" in mem
    def test_get_health(self, monitor):
        health = monitor.get_health()
        assert "cpu_temp_c" in health
        assert "disk_usage" in health
        assert "status" in health
    def test_warnings(self, monitor):
        warnings = monitor.get_warnings()
        assert isinstance(warnings, list)
    def test_status(self, monitor):
        status = monitor.get_status()
        assert status in ("healthy", "warning", "critical")
    def test_summary(self, monitor):
        s = monitor.get_summary()
        assert "cpu_temp" in s
        assert "status" in s
