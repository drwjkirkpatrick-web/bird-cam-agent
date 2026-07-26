"""
core/types.py — Core data types for the Bird Cam Agent.

NOTE: These dataclasses are used across every module in the project.
      They define the shared "vocabulary" — BirdSighting, IdentificationResult,
      RarityLevel, and configuration types.

WHY: Having all types in one place prevents circular imports and ensures
     every module speaks the same language. Subagents building leaf modules
     import from here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RarityLevel(Enum):
    """Bird rarity classification."""

    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"
    ACCIDENTAL = "accidental"

    @classmethod
    def from_string(cls, value: str | None) -> "RarityLevel":
        """Convert a string to RarityLevel, case-insensitive."""
        if not value:
            return cls.COMMON
        normalized = value.strip().lower().replace(" ", "_")
        for member in cls:
            if member.value == normalized:
                return member
        # Common aliases
        aliases = {
            "vr": cls.VERY_RARE,
            "acc": cls.ACCIDENTAL,
            "casual": cls.ACCIDENTAL,
        }
        return aliases.get(normalized, cls.COMMON)

    def __ge__(self, other: "RarityLevel") -> bool:
        """Compare rarity levels — RARE >= COMMON is True."""
        order = list(RarityLevel)
        return order.index(self) >= order.index(other)

    def __le__(self, other: "RarityLevel") -> bool:
        order = list(RarityLevel)
        return order.index(self) <= order.index(other)

    def __gt__(self, other: "RarityLevel") -> bool:
        order = list(RarityLevel)
        return order.index(self) > order.index(other)

    def __lt__(self, other: "RarityLevel") -> bool:
        order = list(RarityLevel)
        return order.index(self) < order.index(other)


@dataclass
class IdentificationResult:
    """
    Result of a bird identification via the Hermes vision bridge.

    NOTE: is_bird=False means the image did not contain a bird.
          The species field will be "Unknown" in that case.
    """

    species: str = "Unknown"
    scientific_name: str = ""
    confidence: float = 0.0
    is_bird: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    alternative_species: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IdentificationResult":
        # NOTE: Filter to known fields — prevents TypeError on unexpected keys
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class BirdSighting:
    """
    A complete bird sighting record — identification + photo + rarity.

    NOTE: sighting_id is auto-generated if not provided.
    """

    sighting_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    species: str = "Unknown"
    scientific_name: str = ""
    confidence: float = 0.0
    photo_path: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    rarity_level: RarityLevel = RarityLevel.COMMON
    notes: str = ""
    location: str = ""
    is_bird: bool = True
    alternative_species: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # NOTE: RarityLevel is an Enum — serialize to string value
        d["rarity_level"] = self.rarity_level.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BirdSighting":
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        # NOTE: Convert rarity string back to enum
        if "rarity_level" in filtered and isinstance(
            filtered["rarity_level"], str
        ):
            filtered["rarity_level"] = RarityLevel.from_string(
                filtered["rarity_level"]
            )
        return cls(**filtered)

    @property
    def is_rare(self) -> bool:
        """True if rarity is RARE or above."""
        return self.rarity_level >= RarityLevel.RARE


@dataclass
class CameraConfig:
    """Camera hardware configuration."""

    device_index: int = 0
    resolution_width: int = 1280
    resolution_height: int = 720
    capture_interval: float = 30.0  # seconds between captures
    photo_dir: str = "data/photos"
    video_dir: str = "data/videos"
    mock_mode: bool = True
    camera_type: str = "auto"  # auto, picamera, usb, mock

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CameraConfig":
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class SightingRecord:
    """Database record for a stored sighting + photo metadata."""

    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sighting_id: str = ""
    stored_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    file_size: int = 0
    file_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SightingRecord":
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


# NOTE: __all__ ensures clean star-imports and documents the public API
__all__ = [
    "RarityLevel",
    "IdentificationResult",
    "BirdSighting",
    "CameraConfig",
    "SightingRecord",
]