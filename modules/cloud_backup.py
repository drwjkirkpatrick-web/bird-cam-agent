"""
modules/cloud_backup.py — Cloud backup for photos and database.

NOTE: Backs up sighting photos and the SQLite database to cloud storage.
      Supports Dropbox, Google Drive, and rsync to a remote server.

WHY: Birdfy and Bird Buddy offer cloud backup. A Pi SD card can fail or
     the Pi could be stolen. Cloud backup ensures sightings aren't lost.
"""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class CloudBackup:
    """
    Cloud backup for bird cam data.

    Usage:
        backup = CloudBackup({
            "provider": "rsync",
            "rsync_dest": "user@server:/backups/bird-cam",
            "mock_mode": True,
        })
        backup.backup_database("data/bird_cam.db")
        backup.backup_photos("data/photos/")
    """

    PROVIDERS = ["dropbox", "gdrive", "rsync", "mock"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.provider = self.config.get("provider", "mock")
        self.mock_mode = self.config.get("mock_mode", True)
        self._backup_count = 0
        self._last_backup = ""

    def backup_database(self, db_path: str) -> bool:
        """Backup the SQLite database."""
        if not os.path.exists(db_path):
            logger.warning("Database not found: %s", db_path)
            return False
        return self._backup_file(db_path, "database")

    def backup_photos(self, photo_dir: str) -> bool:
        """Backup the photos directory."""
        if not os.path.isdir(photo_dir):
            logger.warning("Photo directory not found: %s", photo_dir)
            return False
        return self._backup_dir(photo_dir, "photos")

    def backup_all(self, db_path: str, photo_dir: str) -> dict[str, bool]:
        """Backup database and photos together."""
        return {
            "database": self.backup_database(db_path),
            "photos": self.backup_photos(photo_dir),
        }

    def _backup_file(self, path: str, label: str) -> bool:
        """Backup a single file."""
        if self.mock_mode or self.provider == "mock":
            logger.info("[MOCK] Backup %s: %s (%d bytes)", label, path, os.path.getsize(path))
            self._backup_count += 1
            self._last_backup = datetime.now(timezone.utc).isoformat()
            return True

        if self.provider == "rsync":
            return self._rsync_backup(path, self.config.get("rsync_dest", ""))
        elif self.provider == "dropbox":
            return self._dropbox_backup(path)
        elif self.provider == "gdrive":
            return self._gdrive_backup(path)
        return False

    def _backup_dir(self, path: str, label: str) -> bool:
        """Backup a directory."""
        if self.mock_mode or self.provider == "mock":
            count = sum(len(files) for _, _, files in os.walk(path))
            logger.info("[MOCK] Backup %s: %s (%d files)", label, path, count)
            self._backup_count += 1
            self._last_backup = datetime.now(timezone.utc).isoformat()
            return True

        if self.provider == "rsync":
            dest = self.config.get("rsync_dest", "")
            return self._rsync_backup(path, dest, is_dir=True)
        return False

    def _rsync_backup(self, path: str, dest: str, is_dir: bool = False) -> bool:
        """Backup via rsync to a remote server."""
        if not dest:
            logger.error("No rsync destination configured")
            return False
        try:
            cmd = ["rsync", "-avz", "--delete"]
            if is_dir:
                cmd.append(path + "/")
            else:
                cmd.append(path)
            cmd.append(dest)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                self._backup_count += 1
                self._last_backup = datetime.now(timezone.utc).isoformat()
                logger.info("rsync backup successful: %s", path)
                return True
            logger.error("rsync failed: %s", result.stderr[:200])
            return False
        except Exception as e:
            logger.error("rsync error: %s", e)
            return False

    def _dropbox_backup(self, path: str) -> bool:
        """Backup to Dropbox via API."""
        token = self.config.get("dropbox_token", "")
        if not token:
            return False
        # NOTE: Requires dropbox package: pip install dropbox
        try:
            import dropbox

            dbx = dropbox.Dropbox(token)
            with open(path, "rb") as f:
                dest_path = f"/bird-cam/{os.path.basename(path)}"
                dbx.files_upload(f.read(), dest_path, mode=dropbox.files.WriteMode.overwrite)
            self._backup_count += 1
            self._last_backup = datetime.now(timezone.utc).isoformat()
            return True
        except ImportError:
            logger.warning("dropbox package not installed")
            return False
        except Exception as e:
            logger.error("Dropbox backup failed: %s", e)
            return False

    def _gdrive_backup(self, path: str) -> bool:
        """Backup to Google Drive."""
        # NOTE: Requires google-api-python-client — complex OAuth setup
        logger.warning("Google Drive backup not yet implemented")
        return False

    def get_backup_stats(self) -> dict[str, Any]:
        """Return backup statistics."""
        return {
            "total_backups": self._backup_count,
            "last_backup": self._last_backup,
            "provider": self.provider,
        }


__all__ = ["CloudBackup"]
