"""tests/test_updater.py"""

import pytest
from modules.updater import ProjectUpdater

@pytest.fixture
def updater():
    return ProjectUpdater({"mock_mode": True})

class TestUpdater:
    def test_check_for_updates(self, updater):
        result = updater.check_for_updates()
        assert "updates_available" in result
    def test_update(self, updater):
        result = updater.update()
        assert result["success"] is True
    def test_current_version(self, updater):
        v = updater.get_current_version()
        assert isinstance(v, str)
    def test_changelog(self, updater):
        log = updater.get_changelog()
        assert isinstance(log, list)
        assert len(log) > 0
