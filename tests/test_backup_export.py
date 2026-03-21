"""
Tests for backup_export module
Tests backup creation, restoration, validation, and scheduling
"""

import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from backup_export import (
    DEFAULT_BACKUP_SETTINGS,
    create_backup_bundle,
    list_backups,
    load_backup_settings,
    read_backup_manifest,
    restore_backup_bundle,
    restore_backup_source,
    save_backup_settings,
    should_run_scheduled_backup,
    validate_backup_source,
)


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def sample_db(temp_data_dir):
    """Create a sample database with test data"""
    db_path = temp_data_dir / "memory.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            project TEXT,
            working_dir TEXT,
            provider TEXT,
            model TEXT,
            assistant_label TEXT,
            summary TEXT,
            full_content TEXT,
            importance INTEGER DEFAULT 5,
            status TEXT DEFAULT 'completed',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    for i in range(3):
        conn.execute(
            """INSERT INTO conversations (id, platform, timestamp, summary, full_content, importance)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (f"conv-{i}", "claude_web", datetime.now().isoformat(), f"Summary {i}", f"Content {i}", 7),
        )
    conn.commit()
    yield conn
    try:
        conn.close()
    except Exception:
        pass


class TestBackupSettings:
    """Test backup settings management"""

    def test_default_settings(self, temp_data_dir):
        settings = load_backup_settings(temp_data_dir)
        assert settings["enabled"] is False
        assert settings["interval_hours"] == 24
        assert settings["retention_count"] == 10

    def test_save_and_load_settings(self, temp_data_dir):
        save_backup_settings(temp_data_dir, {"enabled": True, "interval_hours": 12})
        settings = load_backup_settings(temp_data_dir)
        assert settings["enabled"] is True
        assert settings["interval_hours"] == 12

    def test_partial_update(self, temp_data_dir):
        save_backup_settings(temp_data_dir, {"enabled": True})
        settings = load_backup_settings(temp_data_dir)
        assert settings["enabled"] is True
        assert settings["retention_count"] == 10  # Default preserved


class TestShouldRunScheduledBackup:
    """Test backup scheduling logic"""

    def test_disabled_returns_false(self):
        settings = {"enabled": False, "interval_hours": 24, "last_run_at": None}
        assert should_run_scheduled_backup(settings) is False

    def test_no_last_run_returns_true(self):
        settings = {"enabled": True, "interval_hours": 24, "last_run_at": None}
        assert should_run_scheduled_backup(settings) is True

    def test_recent_run_returns_false(self):
        settings = {
            "enabled": True,
            "interval_hours": 24,
            "last_run_at": datetime.now().isoformat(),
        }
        assert should_run_scheduled_backup(settings) is False

    def test_old_run_returns_true(self):
        old_time = datetime.now() - timedelta(hours=25)
        settings = {
            "enabled": True,
            "interval_hours": 24,
            "last_run_at": old_time.isoformat(),
        }
        assert should_run_scheduled_backup(settings) is True

    def test_invalid_last_run_returns_true(self):
        settings = {
            "enabled": True,
            "interval_hours": 24,
            "last_run_at": "not-a-date",
        }
        assert should_run_scheduled_backup(settings) is True


class TestCreateBackupBundle:
    """Test backup creation"""

    def test_creates_backup(self, sample_db, temp_data_dir):
        result = create_backup_bundle(sample_db, temp_data_dir)
        assert "backup_dir" in result
        assert "backup_zip" in result
        assert result["conversation_count"] == 3

    def test_backup_contains_files(self, sample_db, temp_data_dir):
        result = create_backup_bundle(sample_db, temp_data_dir)
        backup_dir = Path(result["backup_dir"])
        assert (backup_dir / "conversations.jsonl").exists()
        assert (backup_dir / "manifest.json").exists()
        assert (backup_dir / "memory.db").exists()

    def test_backup_zip_exists(self, sample_db, temp_data_dir):
        result = create_backup_bundle(sample_db, temp_data_dir)
        assert Path(result["backup_zip"]).exists()

    def test_manifest_content(self, sample_db, temp_data_dir):
        result = create_backup_bundle(sample_db, temp_data_dir)
        manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
        assert manifest["conversation_count"] == 3
        assert "created_at" in manifest
        assert "files" in manifest

    def test_conversations_jsonl_content(self, sample_db, temp_data_dir):
        result = create_backup_bundle(sample_db, temp_data_dir)
        jsonl_path = Path(result["backup_dir"]) / "conversations.jsonl"
        lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3
        first = json.loads(lines[0])
        assert "id" in first
        assert "platform" in first

    def test_updates_settings(self, sample_db, temp_data_dir):
        create_backup_bundle(sample_db, temp_data_dir)
        settings = load_backup_settings(temp_data_dir)
        assert settings["last_run_at"] is not None
        assert settings["last_backup_dir"] is not None
        assert settings["last_error"] == ""


class TestListBackups:
    """Test backup listing"""

    def test_empty_list(self, temp_data_dir):
        backups = list_backups(temp_data_dir)
        assert backups == []

    def test_lists_backups(self, sample_db, temp_data_dir):
        create_backup_bundle(sample_db, temp_data_dir)
        backups = list_backups(temp_data_dir)
        assert len(backups) == 1
        assert "path" in backups[0]
        assert "name" in backups[0]
        assert "modified_at" in backups[0]

    def test_multiple_backups(self, sample_db, temp_data_dir):
        create_backup_bundle(sample_db, temp_data_dir)
        create_backup_bundle(sample_db, temp_data_dir)
        backups = list_backups(temp_data_dir)
        assert len(backups) == 2


class TestRestoreBackup:
    """Test backup restoration"""

    def test_restore_from_directory(self, sample_db, temp_data_dir):
        backup = create_backup_bundle(sample_db, temp_data_dir)
        result = restore_backup_bundle(temp_data_dir, Path(backup["backup_dir"]))
        assert "restored_from" in result
        assert "restored_at" in result
        assert "restored_db_path" in result

    def test_restore_from_zip(self, sample_db, temp_data_dir):
        backup = create_backup_bundle(sample_db, temp_data_dir)
        result = restore_backup_source(temp_data_dir, Path(backup["backup_zip"]))
        assert result["source_type"] == "zip"

    def test_restore_nonexistent_raises(self, temp_data_dir):
        with pytest.raises(FileNotFoundError):
            restore_backup_source(temp_data_dir, Path("/nonexistent/backup"))


class TestValidateBackup:
    """Test backup validation"""

    def test_valid_backup(self, sample_db, temp_data_dir):
        backup = create_backup_bundle(sample_db, temp_data_dir)
        result = validate_backup_source(Path(backup["backup_dir"]))
        assert result["valid"] is True
        assert result["manifest_conversation_count"] == 3
        assert result["jsonl_conversation_count"] == 3

    def test_valid_zip_backup(self, sample_db, temp_data_dir):
        backup = create_backup_bundle(sample_db, temp_data_dir)
        result = validate_backup_source(Path(backup["backup_zip"]))
        assert result["valid"] is True

    def test_nonexistent_source_raises(self):
        with pytest.raises(FileNotFoundError):
            validate_backup_source(Path("/nonexistent"))


class TestReadBackupManifest:
    """Test manifest reading"""

    def test_read_directory_manifest(self, sample_db, temp_data_dir):
        backup = create_backup_bundle(sample_db, temp_data_dir)
        result = read_backup_manifest(Path(backup["backup_dir"]))
        assert result["source_type"] == "directory"
        assert "manifest" in result
        assert result["manifest"]["conversation_count"] == 3

    def test_read_zip_manifest(self, sample_db, temp_data_dir):
        backup = create_backup_bundle(sample_db, temp_data_dir)
        result = read_backup_manifest(Path(backup["backup_zip"]))
        assert result["source_type"] == "zip"
        assert "manifest" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
