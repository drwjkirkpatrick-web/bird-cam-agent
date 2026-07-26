"""core package — shared types and configuration for Bird Cam Agent."""

from core.types import (
    RarityLevel,
    IdentificationResult,
    BirdSighting,
    CameraConfig,
    SightingRecord,
)
from core.config import (
    Config,
    HermesBridgeConfig,
    SMSConfig,
    RarityConfig,
    DatabaseConfig,
    DashboardConfig,
    OrchestratorConfig,
)

__all__ = [
    "RarityLevel",
    "IdentificationResult",
    "BirdSighting",
    "CameraConfig",
    "SightingRecord",
    "Config",
    "HermesBridgeConfig",
    "SMSConfig",
    "RarityConfig",
    "DatabaseConfig",
    "DashboardConfig",
    "OrchestratorConfig",
]