"""
modules/time_lapse.py — Time-lapse compilation from bird cam photos.

NOTE: Creates time-lapse videos or animated GIFs from the bird cam's photo
      collection. Useful for showing a day's worth of feeder activity in
      a few seconds.

WHY: A time-lapse of the feeder over a day or week is visually compelling
     and shows patterns (peak hours, species turnover) that individual
     photos don't reveal.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class TimeLapse:
    """
    Creates time-lapse compilations from bird cam photos.

    Usage:
        tl = TimeLapse(photo_dir="data/photos", output_dir="data/timelapse")
        gif_path = tl.create_gif(date="2026-07-25")
        video_path = tl.create_video(date="2026-07-25", fps=10)
    """

    def __init__(self, photo_dir: str = "data/photos", output_dir: str = "data/timelapse"):
        self.photo_dir = photo_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def get_photos_for_date(self, date: str) -> list[str]:
        """Get all photos from a specific date, sorted by timestamp."""
        photos = []
        if not os.path.exists(self.photo_dir):
            return photos

        for root, dirs, files in os.walk(self.photo_dir):
            for f in files:
                if f.endswith((".jpg", ".jpeg", ".png")):
                    # Check if the file was created on the given date
                    filepath = os.path.join(root, f)
                    try:
                        mtime = os.path.getmtime(filepath)
                        file_date = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
                        if file_date == date:
                            photos.append(filepath)
                    except OSError:
                        pass

        photos.sort()
        return photos

    def get_photos_for_range(self, start_date: str, end_date: str) -> list[str]:
        """Get all photos between two dates (inclusive)."""
        photos = []
        if not os.path.exists(self.photo_dir):
            return photos

        for root, dirs, files in os.walk(self.photo_dir):
            for f in files:
                if f.endswith((".jpg", ".jpeg", ".png")):
                    filepath = os.path.join(root, f)
                    try:
                        mtime = os.path.getmtime(filepath)
                        file_date = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
                        if start_date <= file_date <= end_date:
                            photos.append(filepath)
                    except OSError:
                        pass

        photos.sort()
        return photos

    def create_gif(
        self,
        date: str | None = None,
        photos: list[str] | None = None,
        duration_ms: int = 200,
        max_size: tuple[int, int] = (640, 480),
    ) -> str | None:
        """
        Create an animated GIF from photos.

        Args:
            date: Date string (YYYY-MM-DD). If None, use photos arg.
            photos: List of photo paths. If None, use date.
            duration_ms: Duration per frame in milliseconds.
            max_size: Maximum dimensions for each frame.

        Returns path to the GIF file, or None on failure.
        """
        if photos is None:
            photos = self.get_photos_for_date(date or datetime.now(timezone.utc).strftime("%Y-%m-%d"))

        if not photos:
            logger.warning("No photos found for time-lapse")
            return None

        try:
            from PIL import Image

            frames = []
            for path in photos:
                img = Image.open(path)
                img.thumbnail(max_size)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                frames.append(img)

            if not frames:
                return None

            output_path = os.path.join(
                self.output_dir,
                f"timelapse_{date or 'custom'}.gif"
            )

            frames[0].save(
                output_path,
                save_all=True,
                append_images=frames[1:],
                duration=duration_ms,
                loop=0,
            )
            logger.info("Created time-lapse GIF: %s (%d frames)", output_path, len(frames))
            return output_path

        except ImportError:
            logger.error("PIL not available — cannot create GIF")
            return None
        except Exception as e:
            logger.error("GIF creation failed: %s", e)
            return None

    def create_video(
        self,
        date: str | None = None,
        photos: list[str] | None = None,
        fps: int = 10,
    ) -> str | None:
        """
        Create a time-lapse video from photos using cv2.

        Returns path to the video file, or None on failure.
        """
        if photos is None:
            photos = self.get_photos_for_date(date or datetime.now(timezone.utc).strftime("%Y-%m-%d"))

        if not photos:
            logger.warning("No photos found for time-lapse video")
            return None

        try:
            import cv2

            # Read first frame to get dimensions
            first = cv2.imread(photos[0])
            if first is None:
                logger.error("Cannot read first photo: %s", photos[0])
                return None
            h, w = first.shape[:2]

            output_path = os.path.join(
                self.output_dir,
                f"timelapse_{date or 'custom'}.mp4"
            )

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

            for path in photos:
                frame = cv2.imread(path)
                if frame is not None:
                    writer.write(frame)

            writer.release()
            logger.info("Created time-lapse video: %s (%d frames)", output_path, len(photos))
            return output_path

        except ImportError:
            logger.warning("cv2 not available — cannot create video")
            return None
        except Exception as e:
            logger.error("Video creation failed: %s", e)
            return None

    def get_timelapse_stats(self, date: str) -> dict[str, Any]:
        """Get statistics about photos available for a time-lapse."""
        photos = self.get_photos_for_date(date)
        return {
            "date": date,
            "photo_count": len(photos),
            "estimated_duration_sec": len(photos) / 10 if photos else 0,
            "first_photo": photos[0] if photos else None,
            "last_photo": photos[-1] if photos else None,
        }


__all__ = ["TimeLapse"]