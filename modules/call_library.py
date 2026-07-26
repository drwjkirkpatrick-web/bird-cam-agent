"""
modules/call_library.py — Reference bird call audio library.

NOTE: Stores and plays reference bird call audio for species comparison.
      The user supplies their own audio files — this module organizes them
      and provides playback/search.

WHY: BirdNET has a built-in call library. Having reference calls helps users
     verify audio identifications and learn bird sounds. The user supplies
     their own audio — we provide the organizational tool, not the content.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class CallLibrary:
    """
    Reference bird call audio library.

    Usage:
        library = CallLibrary("data/calls")
        library.add_call("American Robin", "robin_call.mp3", "cheer-up cheerily")
        calls = library.get_calls("American Robin")
    """

    def __init__(self, library_dir: str = "data/calls"):
        self.library_dir = library_dir
        os.makedirs(library_dir, exist_ok=True)
        self._calls: dict[str, list[dict[str, Any]]] = {}

    def add_call(
        self,
        species: str,
        audio_path: str,
        description: str = "",
        call_type: str = "song",
    ) -> bool:
        """Add a reference call to the library."""
        if not os.path.exists(audio_path):
            logger.warning("Audio file not found: %s", audio_path)
            return False

        key = species.lower()
        if key not in self._calls:
            self._calls[key] = []

        entry = {
            "species": species,
            "audio_path": audio_path,
            "description": description,
            "call_type": call_type,
            "file_size": os.path.getsize(audio_path),
        }
        self._calls[key].append(entry)
        logger.info("Added call for %s (%s)", species, call_type)
        return True

    def get_calls(self, species: str) -> list[dict[str, Any]]:
        """Get all reference calls for a species."""
        return list(self._calls.get(species.lower(), []))

    def search_calls(self, query: str) -> list[dict[str, Any]]:
        """Search calls by species name or description."""
        results = []
        query_lower = query.lower()
        for entries in self._calls.values():
            for entry in entries:
                if (query_lower in entry["species"].lower() or
                    query_lower in entry.get("description", "").lower()):
                    results.append(entry)
        return results

    def list_all_species(self) -> list[str]:
        """List all species with calls in the library."""
        return sorted({e["species"] for entries in self._calls.values() for e in entries})

    def get_stats(self) -> dict[str, Any]:
        """Return library statistics."""
        total = sum(len(v) for v in self._calls.values())
        return {
            "total_species": len(self._calls),
            "total_calls": total,
            "species_list": self.list_all_species(),
        }

    def remove_call(self, species: str, audio_path: str) -> bool:
        """Remove a specific call from the library."""
        key = species.lower()
        if key not in self._calls:
            return False
        before = len(self._calls[key])
        self._calls[key] = [e for e in self._calls[key] if e["audio_path"] != audio_path]
        if not self._calls[key]:
            del self._calls[key]
        return len(self._calls.get(key, [])) < before

    @property
    def species_count(self) -> int:
        return len(self._calls)


__all__ = ["CallLibrary"]
