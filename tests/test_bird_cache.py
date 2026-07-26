"""tests/test_bird_cache.py — Bird cache tests."""

import os
import tempfile
import time

import pytest

from core.types import IdentificationResult
from modules.bird_cache import BirdCache


@pytest.fixture
def cache():
    return BirdCache(ttl_seconds=3600, max_entries=100)


@pytest.fixture
def photo(tmp_path):
    p = tmp_path / "test.jpg"
    p.write_bytes(b"\xff\xd8" + b"\x00" * 100 + b"\xff\xd9")
    return str(p)


class TestHash:
    def test_compute_hash(self, cache, photo):
        h = cache.compute_hash(photo)
        assert h is not None
        assert len(h) == 32  # MD5 hex

    def test_hash_missing_file(self, cache):
        assert cache.compute_hash("/nonexistent.jpg") is None

    def test_same_file_same_hash(self, cache, photo):
        h1 = cache.compute_hash(photo)
        h2 = cache.compute_hash(photo)
        assert h1 == h2


class TestGetPut:
    def test_cache_miss(self, cache):
        result = cache.get("nonexistent_key")
        assert result is None
        assert cache.get_stats()["misses"] == 1

    def test_cache_hit(self, cache):
        result = IdentificationResult(species="Robin", confidence=0.9)
        cache.put("key1", result)
        cached = cache.get("key1")
        assert cached is not None
        assert cached.species == "Robin"
        assert cache.get_stats()["hits"] == 1

    def test_cache_ttl_expiry(self):
        c = BirdCache(ttl_seconds=0.1)
        c.put("key", IdentificationResult(species="Robin"))
        time.sleep(0.15)
        assert c.get("key") is None

    def test_cache_clear(self, cache):
        cache.put("key", IdentificationResult(species="Robin"))
        cache.clear()
        assert cache.size == 0

    def test_max_entries_eviction(self):
        c = BirdCache(max_entries=3)
        for i in range(5):
            c.put(f"key{i}", IdentificationResult(species=f"Bird{i}"))
        assert c.size == 3


class TestGetOrIdentify:
    def test_cache_miss_calls_fn(self, cache, photo):
        called = [False]
        def identify_fn(path):
            called[0] = True
            return IdentificationResult(species="Robin", confidence=0.9)
        result = cache.get_or_identify(photo, identify_fn)
        assert called[0] is True
        assert result.species == "Robin"

    def test_cache_hit_skips_fn(self, cache, photo):
        call_count = [0]
        def identify_fn(path):
            call_count[0] += 1
            return IdentificationResult(species="Robin", confidence=0.9)
        cache.get_or_identify(photo, identify_fn)
        cache.get_or_identify(photo, identify_fn)
        assert call_count[0] == 1  # Only called once


class TestStats:
    def test_stats_structure(self, cache):
        stats = cache.get_stats()
        assert "entries" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate_pct" in stats
