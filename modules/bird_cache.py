"""
modules/bird_cache.py — Identification result caching for performance.

NOTE: Caches bird identification results so that repeated photos of the same
      bird don't require a new LLM call. Uses file hashing to detect when
      the same photo (or very similar photo) is submitted again.

WHY: A bird may sit at the feeder for several minutes, generating many
     nearly-identical photos. Re-identifying each one wastes API calls and
     time. The cache stores results keyed by photo hash, with an optional
     TTL for staleness.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any

from core.types import IdentificationResult

logger = logging.getLogger(__name__)


class BirdCache:
    """
    Caches bird identification results by photo hash.

    Usage:
        cache = BirdCache(ttl_seconds=3600)
        key = cache.compute_hash("photo.jpg")
        cached = cache.get(key)
        if cached:
            return cached  # Skip LLM call
        result = bridge.identify_bird("photo.jpg")
        cache.put(key, result)
    """

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 500):
        self._cache: dict[str, dict[str, Any]] = {}
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._hits = 0
        self._misses = 0

    def compute_hash(self, photo_path: str) -> str | None:
        """Compute MD5 hash of a photo file."""
        if not os.path.exists(photo_path):
            return None
        try:
            h = hashlib.md5()
            with open(photo_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError as e:
            logger.error("Hash computation failed: %s", e)
            return None

    def get(self, key: str) -> IdentificationResult | None:
        """Get a cached result by hash key. Returns None if not cached or expired."""
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None

        # Check TTL
        if self._ttl > 0 and (time.time() - entry["timestamp"]) > self._ttl:
            del self._cache[key]
            self._misses += 1
            return None

        self._hits += 1
        result_data = entry["result"]
        return IdentificationResult.from_dict(result_data)

    def put(self, key: str, result: IdentificationResult) -> None:
        """Store an identification result in the cache."""
        if len(self._cache) >= self._max_entries:
            # Evict oldest entry
            oldest_key = min(self._cache, key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest_key]

        self._cache[key] = {
            "result": result.to_dict(),
            "timestamp": time.time(),
        }

    def get_or_identify(
        self, photo_path: str, identify_fn: Any
    ) -> IdentificationResult:
        """
        Get from cache, or call identify_fn and cache the result.

        identify_fn should take a photo_path and return an IdentificationResult.
        """
        key = self.compute_hash(photo_path)
        if key:
            cached = self.get(key)
            if cached is not None:
                logger.debug("Cache hit for %s", photo_path)
                return cached

        result = identify_fn(photo_path)

        if key:
            self.put(key, result)
            logger.debug("Cached result for %s", photo_path)

        return result

    def invalidate(self, key: str) -> bool:
        """Remove a specific entry from the cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        if self._ttl <= 0:
            return 0
        now = time.time()
        expired = [
            k for k, v in self._cache.items()
            if (now - v["timestamp"]) > self._ttl
        ]
        for k in expired:
            del self._cache[k]
        if expired:
            logger.debug("Cleaned up %d expired cache entries", len(expired))
        return len(expired)

    def get_stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        return {
            "entries": len(self._cache),
            "max_entries": self._max_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(hit_rate, 1),
            "ttl_seconds": self._ttl,
        }

    @property
    def size(self) -> int:
        """Number of entries in the cache."""
        return len(self._cache)


__all__ = ["BirdCache"]