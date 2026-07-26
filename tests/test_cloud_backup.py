"""tests/test_cloud_backup.py"""

import os
import pytest
from modules.cloud_backup import CloudBackup

@pytest.fixture
def backup():
    return CloudBackup({"mock_mode": True})

@pytest.fixture
def db_file(tmp_path):
    p = tmp_path / "test.db"
    p.write_bytes(b"SQLite data")
    return str(p)

@pytest.fixture
def photo_dir(tmp_path):
    d = tmp_path / "photos"
    d.mkdir()
    (d / "bird1.jpg").write_bytes(b"photo data")
    return str(d)

class TestBackup:
    def test_backup_database(self, backup, db_file):
        assert backup.backup_database(db_file) is True
    def test_backup_photos(self, backup, photo_dir):
        assert backup.backup_photos(photo_dir) is True
    def test_backup_all(self, backup, db_file, photo_dir):
        results = backup.backup_all(db_file, photo_dir)
        assert results["database"] is True
        assert results["photos"] is True
    def test_missing_db(self, backup):
        assert backup.backup_database("/nonexistent.db") is False
    def test_stats(self, backup, db_file):
        backup.backup_database(db_file)
        stats = backup.get_backup_stats()
        assert stats["total_backups"] == 1
