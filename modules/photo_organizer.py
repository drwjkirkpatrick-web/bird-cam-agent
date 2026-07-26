"""
modules/photo_organizer.py — Photo file management and organization.

NOTE: Organizes bird photos into directories by species and date, manages
      disk space by cleaning up old photos, and provides photo search.

WHY: Bird cams generate a LOT of photos. Without organization, the photo
     directory becomes an unmanageable dump. This module keeps things tidy:
     - Photos organized by species/date
     - Duplicate detection via file hash
     - Disk space management with configurable retention
     - Photo search by species, date, or rarity
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from datetime import datetime, timezone
from typing import Any

from core.types import BirdSighting

logger = logging.getLogger(__name__)


class PhotoOrganizer:
    """
    Organizes and manages bird photo files.

    Usage:
        organizer = PhotoOrganizer(base_dir="data/photos")
        organizer.organize_photo(sighting)
        stats = organizer.get_storage_stats()
        organizer.cleanup_old_photos(max_age_days=90)
    """

    def __init__(self, base_dir: str = "data/photos"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def organize_photo(self, sighting: BirdSighting) -> str | None:
        """
        Move a photo into an organized directory structure:
        base_dir/species/YYYY/MM/photo_filename

        Returns the new path, or None if the photo doesn't exist.
        """
        if not sighting.photo_path or not os.path.exists(sighting.photo_path):
            logger.warning("Photo not found: %s", sighting.photo_path)
            return None

        # Parse the sighting timestamp
        try:
            dt = datetime.fromisoformat(sighting.timestamp.replace("Z", "+00:00"))
            year = str(dt.year)
            month = f"{dt.month:02d}"
        except (ValueError, AttributeError):
            year = "unknown"
            month = "unknown"

        # Create organized directory: base_dir/species/year/month/
        species_dir = sighting.species.replace(" ", "_").replace("/", "_")
        dest_dir = os.path.join(self.base_dir, species_dir, year, month)
        os.makedirs(dest_dir, exist_ok=True)

        filename = os.path.basename(sighting.photo_path)
        dest_path = os.path.join(dest_dir, filename)

        # Don't overwrite if already there
        if os.path.exists(dest_path):
            logger.debug("Photo already organized: %s", dest_path)
            return dest_path

        # Copy (don't move — keep original until verified)
        shutil.copy2(sighting.photo_path, dest_path)
        logger.debug("Organized photo: %s → %s", sighting.photo_path, dest_path)

        return dest_path

    def get_storage_stats(self) -> dict[str, Any]:
        """Return storage statistics for the photo directory."""
        total_size = 0
        total_files = 0
        species_dirs: dict[str, dict[str, int]] = {}

        if not os.path.exists(self.base_dir):
            return {"total_size_bytes": 0, "total_files": 0, "species_dirs": {}}

        for root, dirs, files in os.walk(self.base_dir):
            for f in files:
                if f.endswith((".jpg", ".jpeg", ".png", ".mp4")):
                    filepath = os.path.join(root, f)
                    size = os.path.getsize(filepath)
                    total_size += size
                    total_files += 1

                    # Extract species from directory path
                    rel_path = os.path.relpath(root, self.base_dir)
                    parts = rel_path.split(os.sep)
                    if parts and parts[0] != ".":
                        species = parts[0].replace("_", " ")
                        if species not in species_dirs:
                            species_dirs[species] = {"files": 0, "size_bytes": 0}
                        species_dirs[species]["files"] += 1
                        species_dirs[species]["size_bytes"] += size

        return {
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 1),
            "total_files": total_files,
            "species_dirs": species_dirs,
        }

    def cleanup_old_photos(self, max_age_days: int = 90) -> int:
        """
        Delete photos older than max_age_days.

        Returns the number of files deleted.
        """
        deleted = 0
        now = datetime.now(timezone.utc).timestamp()

        if not os.path.exists(self.base_dir):
            return 0

        for root, dirs, files in os.walk(self.base_dir):
            for f in files:
                if f.endswith((".jpg", ".jpeg", ".png", ".mp4")):
                    filepath = os.path.join(root, f)
                    try:
                        mtime = os.path.getmtime(filepath)
                        age_days = (now - mtime) / 86400
                        if age_days > max_age_days:
                            os.unlink(filepath)
                            deleted += 1
                    except OSError:
                        pass

        # Remove empty directories
        for root, dirs, files in os.walk(self.base_dir, topdown=False):
            if not os.listdir(root) and root != self.base_dir:
                try:
                    os.rmdir(root)
                except OSError:
                    pass

        if deleted:
            logger.info("Cleaned up %d photos older than %d days", deleted, max_age_days)
        return deleted

    def find_duplicates(self) -> list[dict[str, str]]:
        """Find duplicate photos by file hash."""
        hashes: dict[str, list[str]] = {}
        duplicates = []

        for root, dirs, files in os.walk(self.base_dir):
            for f in files:
                if f.endswith((".jpg", ".jpeg", ".png")):
                    filepath = os.path.join(root, f)
                    h = self._file_hash(filepath)
                    if h:
                        if h in hashes:
                            duplicates.append({
                                "original": hashes[h][0],
                                "duplicate": filepath,
                                "hash": h,
                            })
                        else:
                            hashes[h] = [filepath]

        return duplicates

    def search_photos(
        self, species: str | None = None, date: str | None = None
    ) -> list[str]:
        """Search for photos by species and/or date."""
        results = []

        for root, dirs, files in os.walk(self.base_dir):
            for f in files:
                if not f.endswith((".jpg", ".jpeg", ".png")):
                    continue

                filepath = os.path.join(root, f)
                rel_path = os.path.relpath(filepath, self.base_dir)
                parts = rel_path.split(os.sep)

                # Filter by species
                if species and parts:
                    dir_species = parts[0].replace("_", " ")
                    if species.lower() not in dir_species.lower():
                        continue

                # Filter by date (year/month in path)
                if date and len(parts) >= 3:
                    path_date = f"{parts[1]}/{parts[2]}"
                    if date not in path_date:
                        continue

                results.append(filepath)

        return results

    def _file_hash(self, filepath: str) -> str | None:
        """Compute MD5 hash of a file."""
        try:
            h = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None


__all__ = ["PhotoOrganizer"]