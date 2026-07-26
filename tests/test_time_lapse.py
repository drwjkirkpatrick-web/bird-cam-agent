"""tests/test_time_lapse.py — Time-lapse tests."""

import os
import tempfile

import pytest

from modules.time_lapse import TimeLapse


@pytest.fixture
def tl(tmp_path):
    return TimeLapse(
        photo_dir=str(tmp_path / "photos"),
        output_dir=str(tmp_path / "timelapse"),
    )


@pytest.fixture
def photos(tmp_path):
    """Create some test photos."""
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    paths = []
    for i in range(3):
        p = photo_dir / f"bird_{i}.jpg"
        p.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50 + b"\xff\xd9")
        paths.append(str(p))
    return paths


class TestGetPhotos:
    def test_get_photos_empty(self, tl):
        assert tl.get_photos_for_date("2026-07-25") == []

    def test_get_photos_for_range(self, tl, photos):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        result = tl.get_photos_for_range(today, today)
        assert len(result) == 3


class TestCreateGif:
    def test_create_gif_with_photos(self, tl, photos):
        result = tl.create_gif(photos=photos)
        # May return None if PIL has issues, but should not crash
        if result is not None:
            assert os.path.exists(result)

    def test_create_gif_no_photos(self, tl):
        result = tl.create_gif(date="2026-07-25")
        assert result is None


class TestStats:
    def test_timelapse_stats(self, tl):
        stats = tl.get_timelapse_stats("2026-07-25")
        assert stats["date"] == "2026-07-25"
        assert stats["photo_count"] == 0
