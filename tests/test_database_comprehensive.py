"""
Comprehensive database tests for Claude Memory System
Tests cover CRUD operations, edge cases, error handling, and data integrity
"""

import pytest
import os
import sqlite3
from datetime import datetime, timedelta
from backend.database import Database


@pytest.fixture
def test_db():
    """Create a test database instance"""
    db_path = "test_memory_comprehensive.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    db = Database(db_path)
    yield db

    db.conn.close()
    if os.path.exists(db_path):
        os.remove(db_path)


class TestDatabaseSchema:
    """Test database schema creation and structure"""

    def test_all_tables_created(self, test_db):
        """Verify all required tables are created"""
        tables = test_db.get_tables()
        required_tables = [
            "conversations",
            "topics",
            "decisions",
            "preferences",
            "conversation_relations"
        ]
        for table in required_tables:
            assert table in tables, f"Table {table} not found"

    def test_conversations_table_schema(self, test_db):
        """Verify conversations table has correct columns"""
        cursor = test_db.conn.execute("PRAGMA table_info(conversations)")
        columns = {row[1] for row in cursor.fetchall()}

        required_columns = {
            "id", "platform", "timestamp", "project",
            "working_dir", "summary", "full_content",
            "importance", "status", "created_at"
        }
        assert required_columns.issubset(columns)

    def test_indexes_created(self, test_db):
        """Verify performance indexes are created"""
        cursor = test_db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = {row[0] for row in cursor.fetchall()}

        required_indexes = {
            "idx_timestamp",
            "idx_platform",
            "idx_working_dir"
        }
        assert required_indexes.issubset(indexes)


class TestConversationOperations:
    """Test conversation CRUD operations"""

    def test_add_conversation_minimal(self, test_db):
        """Test adding conversation with minimal required fields"""
        conv_id = test_db.add_conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Test conversation"
        )

        assert conv_id is not None
        assert len(conv_id) == 36  # UUID format

    def test_add_conversation_full(self, test_db):
        """Test adding conversation with all fields"""
        now = datetime.now()
        conv_id = test_db.add_conversation(
            platform="claude_code",
            timestamp=now,
            full_content="User: Build a system\nAssistant: Sure!",
            project="test-project",
            working_dir="/home/user/project",
            summary="Building a system",
            importance=8
        )

        assert conv_id is not None

        # Verify data was stored correctly
        conversations = test_db.get_recent_conversations(hours=1)
        assert len(conversations) == 1
        conv = conversations[0]

        assert conv["platform"] == "claude_code"
        assert conv["project"] == "test-project"
        assert conv["working_dir"] == "/home/user/project"
        assert conv["summary"] == "Building a system"
        assert conv["importance"] == 8

    def test_add_multiple_conversations(self, test_db):
        """Test adding multiple conversations"""
        conv_ids = []
        for i in range(5):
            conv_id = test_db.add_conversation(
                platform="claude_web",
                timestamp=datetime.now(),
                full_content=f"Conversation {i}",
                importance=i + 5
            )
            conv_ids.append(conv_id)

        assert len(set(conv_ids)) == 5  # All unique IDs

        conversations = test_db.get_recent_conversations(hours=1, min_importance=0)
        assert len(conversations) == 5


class TestConversationRetrieval:
    """Test conversation retrieval and filtering"""

    def test_get_recent_conversations_time_filter(self, test_db):
        """Test filtering by time window"""
        # Add old conversation
        old_time = datetime.now() - timedelta(hours=48)
        test_db.add_conversation(
            platform="claude_web",
            timestamp=old_time,
            full_content="Old conversation"
        )

        # Add recent conversation
        recent_time = datetime.now()
        test_db.add_conversation(
            platform="claude_web",
            timestamp=recent_time,
            full_content="Recent conversation"
        )

        # Should only get recent one
        conversations = test_db.get_recent_conversations(hours=24, min_importance=0)
        assert len(conversations) == 1
        assert "Recent" in conversations[0]["full_content"]

    def test_get_recent_conversations_importance_filter(self, test_db):
        """Test filtering by importance threshold"""
        test_db.add_conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Low importance",
            importance=3
        )

        test_db.add_conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="High importance",
            importance=9
        )

        # Filter for high importance only
        conversations = test_db.get_recent_conversations(
            hours=1,
            min_importance=7
        )
        assert len(conversations) == 1
        assert conversations[0]["importance"] == 9

    def test_get_recent_conversations_working_dir_filter(self, test_db):
        """Test filtering by working directory"""
        test_db.add_conversation(
            platform="claude_code",
            timestamp=datetime.now(),
            full_content="Project A conversation",
            working_dir="/projects/project-a"
        )

        test_db.add_conversation(
            platform="claude_code",
            timestamp=datetime.now(),
            full_content="Project B conversation",
            working_dir="/projects/project-b"
        )

        # Filter for project A only
        conversations = test_db.get_recent_conversations(
            hours=1,
            min_importance=0,
            working_dir="/projects/project-a"
        )

        assert len(conversations) == 1
        assert conversations[0]["working_dir"] == "/projects/project-a"

    def test_get_recent_conversations_ordering(self, test_db):
        """Test conversations are returned in descending timestamp order"""
        times = [
            datetime.now() - timedelta(minutes=30),
            datetime.now() - timedelta(minutes=20),
            datetime.now() - timedelta(minutes=10)
        ]

        for i, time in enumerate(times):
            test_db.add_conversation(
                platform="claude_web",
                timestamp=time,
                full_content=f"Conversation {i}"
            )

        conversations = test_db.get_recent_conversations(hours=1, min_importance=0)

        # Should be in reverse order (newest first)
        assert "Conversation 2" in conversations[0]["full_content"]
        assert "Conversation 1" in conversations[1]["full_content"]
        assert "Conversation 0" in conversations[2]["full_content"]


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_database_query(self, test_db):
        """Test querying empty database returns empty list"""
        conversations = test_db.get_recent_conversations(hours=24)
        assert conversations == []

    def test_very_long_content(self, test_db):
        """Test handling very long conversation content"""
        long_content = "A" * 100000  # 100KB of text

        conv_id = test_db.add_conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content=long_content
        )

        conversations = test_db.get_recent_conversations(hours=1, min_importance=0)
        assert len(conversations[0]["full_content"]) == 100000

    def test_special_characters_in_content(self, test_db):
        """Test handling special characters and unicode"""
        special_content = "Test with 'quotes', \"double quotes\", and unicode: 你好 🎉"

        conv_id = test_db.add_conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content=special_content
        )

        conversations = test_db.get_recent_conversations(hours=1, min_importance=0)
        assert conversations[0]["full_content"] == special_content

    def test_null_optional_fields(self, test_db):
        """Test that optional fields can be null"""
        conv_id = test_db.add_conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Test",
            project=None,
            working_dir=None,
            summary=None
        )

        conversations = test_db.get_recent_conversations(hours=1, min_importance=0)
        conv = conversations[0]

        assert conv["project"] is None
        assert conv["working_dir"] is None
        assert conv["summary"] is None

    def test_extreme_importance_values(self, test_db):
        """Test boundary values for importance"""
        # Test minimum
        test_db.add_conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Min importance",
            importance=0
        )

        # Test maximum
        test_db.add_conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Max importance",
            importance=10
        )

        conversations = test_db.get_recent_conversations(hours=1, min_importance=0)
        assert len(conversations) == 2

        importances = {conv["importance"] for conv in conversations}
        assert 0 in importances
        assert 10 in importances


class TestDataIntegrity:
    """Test data integrity and consistency"""

    def test_conversation_id_uniqueness(self, test_db):
        """Test that conversation IDs are unique"""
        ids = set()
        for i in range(100):
            conv_id = test_db.add_conversation(
                platform="claude_web",
                timestamp=datetime.now(),
                full_content=f"Test {i}"
            )
            ids.add(conv_id)

        assert len(ids) == 100  # All unique

    def test_timestamp_persistence(self, test_db):
        """Test that timestamps are stored and retrieved correctly"""
        test_time = datetime(2024, 3, 9, 15, 30, 45)

        test_db.add_conversation(
            platform="claude_web",
            timestamp=test_time,
            full_content="Test"
        )

        conversations = test_db.get_recent_conversations(hours=24*365, min_importance=0)
        stored_timestamp = conversations[0]["timestamp"]

        # SQLite stores as string, so compare string representation
        assert test_time.strftime("%Y-%m-%d %H:%M:%S") in stored_timestamp

    def test_concurrent_writes(self, test_db):
        """Test that multiple writes don't corrupt data"""
        # Simulate rapid consecutive writes
        for i in range(50):
            test_db.add_conversation(
                platform="claude_web",
                timestamp=datetime.now(),
                full_content=f"Concurrent write {i}"
            )

        conversations = test_db.get_recent_conversations(hours=1, min_importance=0)
        assert len(conversations) == 50


class TestPlatformSupport:
    """Test support for different Claude platforms"""

    def test_all_platforms(self, test_db):
        """Test storing conversations from all platforms"""
        platforms = ["claude_web", "claude_code", "antigravity"]

        for platform in platforms:
            test_db.add_conversation(
                platform=platform,
                timestamp=datetime.now(),
                full_content=f"Test from {platform}"
            )

        conversations = test_db.get_recent_conversations(hours=1, min_importance=0)
        stored_platforms = {conv["platform"] for conv in conversations}

        assert stored_platforms == set(platforms)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
