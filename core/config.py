"""
core/config.py — Configuration loader for Bird Cam Agent.

NOTE: This module loads YAML configuration and maps it to a frozen Config
      dataclass with nested sub-configs. Every module reads its settings
      from here.

WHY: Centralized config prevents scattered hardcoded values and makes the
     agent portable across different Pi models and deployment scenarios.
     The mock_mode flags let everything run on a dev machine with no hardware.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from typing import Any

from core.types import CameraConfig


@dataclass(frozen=True)
class HermesBridgeConfig:
    """Hermes Agent vision bridge configuration."""

    mode: str = "mock"  # api, cli, mock
    api_url: str = "http://127.0.0.1:9119"
    api_key: str = ""
    model: str = ""  # empty = use Hermes default vision model
    timeout: int = 30  # seconds
    mock_mode: bool = True
    confidence_threshold: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HermesBridgeConfig":
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass(frozen=True)
class SMSConfig:
    """SMS notification configuration."""

    provider: str = "mock"  # twilio, hermes_gateway, mock
    account_sid: str = ""
    auth_token: str = ""
    from_number: str = ""
    to_number: str = ""
    mock_mode: bool = True
    cooldown_minutes: int = 30  # min between alerts for same species

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SMSConfig":
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass(frozen=True)
class RarityConfig:
    """Rarity checker configuration."""

    rarity_file: str = ""  # path to user-supplied YAML
    location_name: str = ""
    default_rarity: str = "common"  # fallback for unknown species

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RarityConfig":
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass(frozen=True)
class DatabaseConfig:
    """SQLite database configuration."""

    db_path: str = "data/bird_cam.db"
    photo_dir: str = "data/photos"
    video_dir: str = "data/videos"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DatabaseConfig":
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass(frozen=True)
class DashboardConfig:
    """Flask dashboard configuration."""

    host: str = "0.0.0.0"
    port: int = 9195
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DashboardConfig":
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass(frozen=True)
class OrchestratorConfig:
    """Main orchestrator loop configuration."""

    capture_interval: float = 30.0  # seconds between captures
    identification_enabled: bool = True
    notification_enabled: bool = True
    recording_enabled: bool = False
    record_duration: float = 10.0  # seconds of video per sighting
    mock_mode: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrchestratorConfig":
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass(frozen=True)
class Config:
    """
    Top-level configuration for the Bird Cam Agent.

    NOTE: All sub-configs default to mock_mode=True so the agent runs
          out of the box on any machine without hardware.
    """

    camera: CameraConfig = field(default_factory=CameraConfig)
    hermes_bridge: HermesBridgeConfig = field(default_factory=HermesBridgeConfig)
    sms: SMSConfig = field(default_factory=SMSConfig)
    rarity: RarityConfig = field(default_factory=RarityConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera": self.camera.to_dict(),
            "hermes_bridge": self.hermes_bridge.to_dict(),
            "sms": self.sms.to_dict(),
            "rarity": self.rarity.to_dict(),
            "database": self.database.to_dict(),
            "dashboard": self.dashboard.to_dict(),
            "orchestrator": self.orchestrator.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        """Build Config from a dict (e.g. parsed YAML)."""
        # NOTE: Each sub-config handles its own field filtering
        return cls(
            camera=CameraConfig.from_dict(data.get("camera", {})),
            hermes_bridge=HermesBridgeConfig.from_dict(
                data.get("hermes_bridge", {})
            ),
            sms=SMSConfig.from_dict(data.get("sms", {})),
            rarity=RarityConfig.from_dict(data.get("rarity", {})),
            database=DatabaseConfig.from_dict(data.get("database", {})),
            dashboard=DashboardConfig.from_dict(data.get("dashboard", {})),
            orchestrator=OrchestratorConfig.from_dict(
                data.get("orchestrator", {})
            ),
        )

    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        """Load configuration from a YAML file."""
        import yaml

        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        return cls.from_dict(data)

    @classmethod
    def create_default_config(cls) -> "Config":
        """
        Create a Config with sensible defaults for a Raspberry Pi.

        NOTE: Everything starts in mock_mode=True so the user can test
              before connecting real hardware.
        """
        return cls()

    @classmethod
    def write_default_config(cls, path: str) -> None:
        """Write a YAML config template to the given path."""
        default = cls.create_default_config()
        import yaml

        with open(path, "w") as f:
            yaml.dump(default.to_dict(), f, default_flow_style=False, sort_keys=True)


__all__ = [
    "Config",
    "HermesBridgeConfig",
    "SMSConfig",
    "RarityConfig",
    "DatabaseConfig",
    "DashboardConfig",
    "OrchestratorConfig",
]