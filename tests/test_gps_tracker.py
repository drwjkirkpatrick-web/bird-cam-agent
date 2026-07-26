"""tests/test_gps_tracker.py"""

import pytest
from modules.gps_tracker import GPSTracker, GPSReading

@pytest.fixture
def tracker():
    return GPSTracker({"mock_mode": True})

class TestGPS:
    def test_get_location(self, tracker):
        reading = tracker.get_location()
        assert isinstance(reading, GPSReading)
        assert reading.latitude != 0 or reading.fix_quality == "mock"
    def test_static_location(self):
        t = GPSTracker({"static_lat": 45.28, "static_lon": -122.37})
        reading = t.get_location()
        assert reading.latitude == 45.28
        assert reading.longitude == -122.37
        assert reading.fix_quality == "static"
    def test_location_dict(self, tracker):
        d = tracker.get_location_dict()
        assert "latitude" in d
        assert "longitude" in d
    def test_has_fix(self, tracker):
        assert isinstance(tracker.has_fix, bool)
