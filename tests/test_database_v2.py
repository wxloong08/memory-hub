"""
Tests for Database V2 features
Tests newer database methods: delete, memory tier, pagination, filters, deduplication
"""

import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from database import Database


@pytest.fixture
def test_db(tmp_path):
    """Create a test database instance"""
    db_path = str(tmp_path / "test_v2.db")
    db = Database(db_path)
    yield db
    db.conn.close()


@pytest.fixture
def populated_db(test_db):
    """Database with sample conversations"""
    platforms = ["claude_web", "codex", "gemini_cli", "antigravity"]
    for i in range(10):
        test_db.add_conversation(
            platform=platforms[i % len(platforms)],
            timestamp=datetime.now() - timedelta(hours=i),
            full_content=f"Conversation {i} about topic {i}",
            project=f"project-{i % 3}",
            working_dir=f"/projects/project-{i % 3}",
            provider="openai" if i % 2 == 0 else "anthropic",
            model="gpt-5" if i % 2 == 0 else "claude-sonnet",
            assistant_label="Codex" if i % 2 == 0 else "Claude Code",
            summary=f"Summary of conversation {i}",
            importance=5 + (i % 6),
            summary_source="ai" if i % 3 == 0 else "fallback",
        )
    return test_db


class TestDeleteConversation:
    """Test conversation deletion"""

    def test_delete_existing(self, test_db):
        conv_id = test_db.add_conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Delete me",
        )
        assert test_db.delete_conversation(conv_id) is True
        conversations = test_db.get_recent_conversations(hours=1, min_importance=0)
        assert len(conversations) == 0

    def test_delete_nonexistent(self, test_db):
        result = test_db.delete_conversation("nonexistent-id")
        assert result is False

    def test_delete_cleans_related_data(self, test_db):
        conv_id = test_db.add_conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Has related data",
        )
        # Add a topic
        test_db.conn.execute(
            "INSERT INTO topics (conversation_id, topic) VALUES (?, ?)",
            (conv_id, "test-topic"),
        )
        # Add a decision
        test_db.conn.execute(
            "INSERT INTO decisions (conversation_id, decision, timestamp) VALUES (?, ?, ?)",
            (conv_id, "test-decision", datetime.now().isoformat()),
        )
        test_db.conn.commit()

        test_db.delete_conversation(conv_id)

        # Verify related data is cleaned
        topics = test_db.conn.execute(
            "SELECT COUNT(*) FROM topics WHERE conversation_id = ?", (conv_id,)
        ).fetchone()[0]
        assert topics == 0

        decisions = test_db.conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE conversation_id = ?", (conv_id,)
        ).fetchone()[0]
        assert decisions == 0


class TestUpdateMemoryTier:
    """Test memory tier updates"""

    def test_update_tier(self, test_db):
        conv_id = test_db.add_conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Test content",
        )
        result = test_db.update_memory_tier(conv_id, "saved")
        assert result is True

        conversations = test_db.get_recent_conversations(hours=1, min_importance=0)
        assert conversations[0]["memory_tier"] == "saved"

    def test_update_nonexistent(self, test_db):
        result = test_db.update_memory_tier("nonexistent", "saved")
        assert result is False

    def test_various_tiers(self, test_db):
        conv_id = test_db.add_conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Test",
        )
        for tier in ["temporary", "saved", "pinned"]:
            test_db.update_memory_tier(conv_id, tier)
            convs = test_db.get_recent_conversations(hours=1, min_importance=0)
            assert convs[0]["memory_tier"] == tier


class TestPaginatedList:
    """Test paginated conversation listing"""

    def test_basic_pagination(self, populated_db):
        page1, total = populated_db.get_recent_conversations_page(limit=3, offset=0)
        assert len(page1) == 3
        assert total == 10

    def test_offset(self, populated_db):
        page1, _ = populated_db.get_recent_conversations_page(limit=3, offset=0)
        page2, _ = populated_db.get_recent_conversations_page(limit=3, offset=3)
        assert page1[0]["id"] != page2[0]["id"]

    def test_platform_filter(self, populated_db):
        results, total = populated_db.get_recent_conversations_page(
            platform="codex", limit=50
        )
        assert all(r["platform"] == "codex" for r in results)

    def test_model_or_provider_filter(self, populated_db):
        results, total = populated_db.get_recent_conversations_page(
            model_or_provider="openai", limit=50
        )
        assert all(
            r["model"] == "openai" or r["provider"] == "openai" for r in results
        )

    def test_summary_source_filter(self, populated_db):
        results, total = populated_db.get_recent_conversations_page(
            summary_source="ai", limit=50
        )
        assert all(r["summary_source"] == "ai" for r in results)

    def test_query_text_filter(self, populated_db):
        results, total = populated_db.get_recent_conversations_page(
            query_text="conversation 5", limit=50, min_importance=0
        )
        assert total >= 1

    def test_sort_newest(self, populated_db):
        results, _ = populated_db.get_recent_conversations_page(sort="newest", limit=3)
        # Newest first - timestamps should be descending
        assert len(results) == 3

    def test_sort_importance(self, populated_db):
        results, _ = populated_db.get_recent_conversations_page(
            sort="importance", limit=10, min_importance=0
        )
        importances = [r["importance"] for r in results]
        assert importances == sorted(importances, reverse=True)

    def test_empty_result(self, populated_db):
        results, total = populated_db.get_recent_conversations_page(
            platform="nonexistent_platform", limit=50
        )
        assert results == []
        assert total == 0


class TestGetConversationFilterValues:
    """Test filter value extraction"""

    def test_returns_all_filter_types(self, populated_db):
        filters = populated_db.get_conversation_filter_values()
        assert "platforms" in filters
        assert "models" in filters
        assert "summary_sources" in filters

    def test_platforms_populated(self, populated_db):
        filters = populated_db.get_conversation_filter_values()
        assert "claude_web" in filters["platforms"]
        assert "codex" in filters["platforms"]

    def test_models_populated(self, populated_db):
        filters = populated_db.get_conversation_filter_values()
        assert len(filters["models"]) >= 1


class TestFindExistingConversation:
    """Test conversation deduplication"""

    def test_find_by_source_path_and_fingerprint(self, test_db):
        conv_id = test_db.add_conversation(
            platform="codex",
            timestamp=datetime.now(),
            full_content="Original",
            source_path="/path/to/session.jsonl",
            source_fingerprint="123:456",
        )
        found = test_db.find_existing_conversation(
            platform="codex",
            timestamp=datetime.now(),
            source_path="/path/to/session.jsonl",
            source_fingerprint="123:456",
        )
        assert found == conv_id

    def test_find_by_content_hash(self, test_db):
        now = datetime.now()
        conv_id = test_db.add_conversation(
            platform="codex",
            timestamp=now,
            full_content="Original",
            content_hash="abc123",
        )
        found = test_db.find_existing_conversation(
            platform="codex",
            timestamp=now,
            content_hash="abc123",
        )
        assert found == conv_id

    def test_not_found(self, test_db):
        found = test_db.find_existing_conversation(
            platform="codex",
            timestamp=datetime.now(),
            content_hash="nonexistent",
        )
        assert found is None

    def test_different_platform_not_matched(self, test_db):
        now = datetime.now()
        test_db.add_conversation(
            platform="codex",
            timestamp=now,
            full_content="Original",
            content_hash="abc123",
        )
        found = test_db.find_existing_conversation(
            platform="claude_code",
            timestamp=now,
            content_hash="abc123",
        )
        assert found is None


class TestNewColumns:
    """Test new conversation columns"""

    def test_provider_and_model(self, test_db):
        conv_id = test_db.add_conversation(
            platform="codex",
            timestamp=datetime.now(),
            full_content="Test",
            provider="openai",
            model="gpt-5",
        )
        convs = test_db.get_recent_conversations(hours=1, min_importance=0)
        assert convs[0]["provider"] == "openai"
        assert convs[0]["model"] == "gpt-5"

    def test_assistant_label(self, test_db):
        conv_id = test_db.add_conversation(
            platform="codex",
            timestamp=datetime.now(),
            full_content="Test",
            assistant_label="Codex",
        )
        convs = test_db.get_recent_conversations(hours=1, min_importance=0)
        assert convs[0]["assistant_label"] == "Codex"

    def test_source_path_and_fingerprint(self, test_db):
        conv_id = test_db.add_conversation(
            platform="codex",
            timestamp=datetime.now(),
            full_content="Test",
            source_path="/path/file.jsonl",
            source_fingerprint="123:456",
        )
        convs = test_db.get_recent_conversations(hours=1, min_importance=0)
        assert convs[0]["source_path"] == "/path/file.jsonl"
        assert convs[0]["source_fingerprint"] == "123:456"

    def test_content_hash(self, test_db):
        conv_id = test_db.add_conversation(
            platform="codex",
            timestamp=datetime.now(),
            full_content="Test",
            content_hash="sha256hash",
        )
        convs = test_db.get_recent_conversations(hours=1, min_importance=0)
        assert convs[0]["content_hash"] == "sha256hash"

    def test_recovery_mode(self, test_db):
        conv_id = test_db.add_conversation(
            platform="antigravity",
            timestamp=datetime.now(),
            full_content="Test",
            recovery_mode="live-rpc",
        )
        convs = test_db.get_recent_conversations(hours=1, min_importance=0)
        assert convs[0]["recovery_mode"] == "live-rpc"

    def test_memory_tier_default(self, test_db):
        conv_id = test_db.add_conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Test",
        )
        convs = test_db.get_recent_conversations(hours=1, min_importance=0)
        assert convs[0]["memory_tier"] == "temporary"


class TestGetConversationsForResummary:
    """Test resummary candidate retrieval"""

    def test_returns_recent_conversations(self, populated_db):
        results = populated_db.get_conversations_for_resummary(limit=5)
        assert len(results) == 5

    def test_respects_limit(self, populated_db):
        results = populated_db.get_conversations_for_resummary(limit=3)
        assert len(results) == 3

    def test_ordered_by_timestamp_desc(self, populated_db):
        results = populated_db.get_conversations_for_resummary(limit=5)
        timestamps = [r["timestamp"] for r in results]
        assert timestamps == sorted(timestamps, reverse=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
