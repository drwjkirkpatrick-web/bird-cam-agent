"""tests/test_config.py — Configuration tests."""

import os
import tempfile

from core.config import (
    Config,
    HermesBridgeConfig,
    SMSConfig,
    RarityConfig,
    DatabaseConfig,
    DashboardConfig,
    OrchestratorConfig,
)
from core.types import CameraConfig


class TestConfig:
    def test_default_config_all_mock(self):
        config = Config.create_default_config()
        assert config.camera.mock_mode is True
        assert config.hermes_bridge.mock_mode is True
        assert config.sms.mock_mode is True
        assert config.orchestrator.mock_mode is True

    def test_round_trip(self):
        config = Config.create_default_config()
        d = config.to_dict()
        restored = Config.from_dict(d)
        assert restored.camera.mock_mode == config.camera.mock_mode
        assert restored.hermes_bridge.mode == config.hermes_bridge.mode
        assert restored.dashboard.port == config.dashboard.port

    def test_from_dict_partial(self):
        data = {"camera": {"mock_mode": False, "resolution_width": 1920}}
        config = Config.from_dict(data)
        assert config.camera.mock_mode is False
        assert config.camera.resolution_width == 1920
        # Other configs use defaults
        assert config.hermes_bridge.mock_mode is True

    def test_from_dict_ignores_unknown_keys(self):
        data = {"camera": {"mock_mode": True, "bogus_field": "ignored"}}
        config = Config.from_dict(data)
        assert config.camera.mock_mode is True

    def test_from_yaml(self):
        import yaml

        yaml_str = """
camera:
  mock_mode: false
  resolution_width: 1920
  resolution_height: 1080
hermes_bridge:
  mode: api
  api_url: http://localhost:9119
sms:
  provider: twilio
  to_number: '+15035551234'
dashboard:
  port: 8080
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_str)
            f.flush()
            path = f.name

        try:
            config = Config.from_yaml(path)
            assert config.camera.mock_mode is False
            assert config.camera.resolution_width == 1920
            assert config.hermes_bridge.mode == "api"
            assert config.sms.provider == "twilio"
            assert config.dashboard.port == 8080
        finally:
            os.unlink(path)

    def test_write_default_config(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            path = f.name

        try:
            Config.write_default_config(path)
            assert os.path.exists(path)
            # Verify it can be loaded back
            config = Config.from_yaml(path)
            assert config.camera.mock_mode is True
        finally:
            os.unlink(path)


class TestSubConfigs:
    def test_hermes_bridge_config(self):
        config = HermesBridgeConfig(mode="api", api_url="http://test:9999")
        assert config.mode == "api"
        assert config.api_url == "http://test:9999"

    def test_sms_config(self):
        config = SMSConfig(provider="twilio", to_number="+15035551234")
        assert config.provider == "twilio"
        assert config.to_number == "+15035551234"
        assert config.cooldown_minutes == 30

    def test_dashboard_config(self):
        config = DashboardConfig(port=9195)
        assert config.port == 9195
        assert config.enabled is True