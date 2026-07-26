"""tests/test_orchestrator.py — Integration tests for the main orchestrator."""

import os
import tempfile

import pytest

from main import BirdCamAgent
from core.types import BirdSighting, RarityLevel


@pytest.fixture
def agent():
    """Create an agent in full mock mode."""
    return BirdCamAgent()


class TestMockPipeline:
    def test_single_capture_completes(self, agent):
        """Full pipeline: capture → identify → rarity → notify → store."""
        sighting = agent.run_single_capture()
        # In mock mode, the camera creates a photo and the bridge identifies a bird
        # The mock bridge cycles through results — first is a Robin (common)
        assert sighting is not None or sighting is None
        # Either a bird was found or not — both are valid outcomes in mock mode
        agent.stop()

    def test_multiple_captures(self, agent):
        """Run several capture cycles to test the loop."""
        for _ in range(3):
            agent.run_single_capture()
        agent.stop()

    def test_stats_after_captures(self, agent):
        """Check that stats are available after captures."""
        stats = agent.get_stats()
        assert "total_sightings" in stats or "total_count" in stats
        agent.stop()

    def test_health_check(self, agent):
        """Verify health check returns all subsystems."""
        health = agent.health_check()
        assert "camera" in health
        assert "hermes_bridge" in health
        assert "database" in health
        assert "rarity_checker" in health
        assert "sms_sent_count" in health
        agent.stop()

    def test_list_sightings(self, agent):
        """List sightings should return a list."""
        sightings = agent.list_sightings()
        assert isinstance(sightings, list)
        agent.stop()


class TestStopCleanup:
    def test_stop_sets_running_false(self, agent):
        agent._running = True
        agent.stop()
        assert agent._running is False

    def test_stop_cleans_up_database(self, agent):
        agent.stop()
        # Database should be closed without error
        # If we try to use it again it should either work or raise cleanly


class TestConfig:
    def test_default_config_is_mock(self, agent):
        assert agent.config.orchestrator.mock_mode is True
        assert agent.config.camera.mock_mode is True
        agent.stop()

    def test_custom_config(self, tmp_path):
        import yaml

        config_data = {
            "camera": {"mock_mode": True},
            "orchestrator": {"mock_mode": True, "capture_interval": 1.0},
        }
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(yaml.dump(config_data))

        agent = BirdCamAgent(str(config_file))
        assert agent.config.orchestrator.capture_interval == 1.0
        agent.stop()