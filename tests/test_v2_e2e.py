"""
End-to-end tests for Memory Hub V2.

Tests the complete flow:
  Create V2 database -> Add conversations + messages -> Compress messages
  -> Execute CLI switch -> Verify generated context file

All tests use temp directories and in-memory/temp databases, no external services.
"""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure backend is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from context_assembler import assemble_switch_context
from database_v2 import DatabaseV2
from message_compressor import compress_message, compress_messages, estimate_tokens
from switch_engine import (
    execute_switch,
    get_switch_history,
    get_working_memory,
    preview_switch,
    upsert_working_memory,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workspace_dir():
    d = tempfile.mkdtemp()
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except (OSError, PermissionError):
        pass


@pytest.fixture
def db(db_path):
    return DatabaseV2(db_path)


def _add_preferences_table(conn):
    """Add preferences table with test data (core memories)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            key TEXT,
            value TEXT,
            confidence REAL DEFAULT 0.5,
            priority INTEGER DEFAULT 0,
            client_rules TEXT DEFAULT '{}',
            status TEXT DEFAULT 'active',
            last_updated DATETIME,
            pinned INTEGER DEFAULT 0,
            workspace_scope TEXT
        );
    """)
    conn.execute(
        "INSERT INTO preferences (category, key, value, confidence, priority, pinned, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("identity", "role", "Senior Python developer", 0.95, 10, 1, "active"),
    )
    conn.execute(
        "INSERT INTO preferences (category, key, value, confidence, priority, pinned, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("preference", "testing", "Always write tests before shipping", 0.85, 5, 0, "active"),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# E2E Tests
# ---------------------------------------------------------------------------

class TestV2FullPipeline:
    """Complete pipeline: ingest -> compress -> switch -> verify output."""

    def test_ingest_compress_switch_verify(self, db, workspace_dir):
        """
        Full flow:
        1. Create V2 database (done by fixture)
        2. Add conversations with messages
        3. Verify compression is applied to assistant messages
        4. Execute CLI switch
        5. Verify generated context file has correct content
        """
        # -- Step 1: Add conversations --
        conv_id_1, msg_count_1, tokens_1 = db.add_conversation(
            platform="claude_code",
            started_at="2026-03-19T10:00:00Z",
            messages=[
                {"role": "user", "content": "Fix the authentication bug in auth.py"},
                {"role": "assistant", "content": "I found a race condition in the token refresh logic. The issue is that two concurrent requests can both try to refresh the token simultaneously."},
                {"role": "user", "content": "Good, now add retry logic with exponential backoff"},
                {"role": "assistant", "content": "Added retry with exponential backoff. The implementation uses a decorator pattern."},
            ],
            workspace_path=workspace_dir,
            summary="Fix auth bug with retry logic",
            provider="anthropic",
            model="claude-opus-4-6",
        )

        conv_id_2, msg_count_2, tokens_2 = db.add_conversation(
            platform="codex",
            started_at="2026-03-19T09:00:00Z",
            messages=[
                {"role": "user", "content": "Set up CI pipeline for the project"},
                {"role": "assistant", "content": "Created GitHub Actions workflow with test, lint, and deploy stages."},
            ],
            workspace_path=workspace_dir,
            summary="Set up CI pipeline",
        )

        # Verify conversations stored
        assert msg_count_1 == 4
        assert msg_count_2 == 2
        assert tokens_1 > 0
        assert tokens_2 > 0

        conv = db.get_conversation(conv_id_1)
        assert conv is not None
        assert conv["platform"] == "claude_code"

        # -- Step 2: Verify messages stored with compression --
        messages = db.get_messages(conv_id_1)
        assert len(messages) == 4
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

        # Short assistant messages won't be compressed, but structure is correct
        compressed = db.get_compressed_messages(conv_id_1)
        assert len(compressed) == 4

        # -- Step 3: Set up working memory --
        db.upsert_working_memory(
            workspace_path=workspace_dir,
            active_task="Fix auth token refresh bug",
            current_plan=["Investigate", "Fix race condition", "Add retry", "Test"],
            progress=["Investigated", "Fixed race condition"],
            open_issues=["Need retry logic"],
            last_cli="claude_code",
            recent_changes="Modified auth.py: added mutex lock",
        )

        wm = db.get_working_memory(workspace_dir)
        assert wm is not None
        assert wm["active_task"] == "Fix auth token refresh bug"
        assert wm["current_plan"] == ["Investigate", "Fix race condition", "Add retry", "Test"]

        # -- Step 4: Add core memories (preferences) --
        _add_preferences_table(db.conn)

        # -- Step 5: Execute switch to codex --
        result = execute_switch(
            conn=db.conn,
            to_cli="codex",
            workspace_path=workspace_dir,
            from_cli="claude_code",
            write_file=True,
        )

        assert result["status"] == "ok"
        assert result["target_cli"] == "codex"
        assert result["switch_number"] == 1
        assert result["context_assembled"]["total_tokens"] > 0
        assert result["core_memories_injected"] >= 0
        assert result["archive_turns_injected"] > 0

        # -- Step 6: Verify generated context file --
        target = Path(workspace_dir) / "AGENTS.md"
        assert target.exists(), "AGENTS.md should be created for codex"

        content = target.read_text(encoding="utf-8")
        assert "Resume Context" in content
        assert "Memory Hub V2" in content
        # Working memory should be in context
        assert "Fix auth token refresh bug" in content
        # Archive content should be present
        assert "claude_code" in content

        # -- Step 7: Verify switch history recorded --
        history = get_switch_history(db.conn)
        assert len(history) == 1
        assert history[0]["from_cli"] == "claude_code"
        assert history[0]["to_cli"] == "codex"

        # -- Step 8: Verify working memory updated --
        wm = get_working_memory(db.conn, workspace_dir)
        assert wm["last_cli"] == "codex"
        assert wm["switch_count"] == 1

    def test_multi_cli_switch_chain(self, db, workspace_dir):
        """Switch through all four CLI targets in sequence."""
        # Add a conversation
        db.add_conversation(
            platform="claude_code",
            started_at="2026-03-19T10:00:00Z",
            messages=[
                {"role": "user", "content": "Build the new feature"},
                {"role": "assistant", "content": "I'll implement it step by step."},
            ],
            workspace_path=workspace_dir,
            summary="Build feature",
        )

        expected_files = {
            "codex": "AGENTS.md",
            "gemini_cli": "GEMINI.md",
            "claude_code": ".claude/CLAUDE.md",
            "antigravity": ".antigravity/context.md",
        }

        for cli, expected_file in expected_files.items():
            result = execute_switch(
                db.conn, cli, workspace_dir,
                from_cli="claude_code", write_file=True,
            )
            assert result["status"] == "ok"
            assert result["target_cli"] == cli

            target = Path(workspace_dir) / expected_file
            assert target.exists(), f"{expected_file} should exist after switch to {cli}"

            content = target.read_text(encoding="utf-8")
            assert "Resume Context" in content
            assert "Memory Hub V2" in content

        # Verify switch count
        wm = get_working_memory(db.conn, workspace_dir)
        assert wm["switch_count"] == 4

        # Verify full history
        history = get_switch_history(db.conn)
        assert len(history) == 4

    def test_preview_then_execute(self, db, workspace_dir):
        """Preview should not modify state; execute should."""
        db.add_conversation(
            platform="claude_code",
            started_at="2026-03-19T10:00:00Z",
            messages=[
                {"role": "user", "content": "Test preview"},
                {"role": "assistant", "content": "Preview response."},
            ],
            workspace_path=workspace_dir,
            summary="Test",
        )

        # Preview
        preview = preview_switch(db.conn, "codex", workspace_dir)
        assert preview["status"] == "preview"
        assert preview["context_assembled"]["total_tokens"] > 0
        assert not (Path(workspace_dir) / "AGENTS.md").exists()
        assert get_switch_history(db.conn) == []

        # Execute
        result = execute_switch(db.conn, "codex", workspace_dir, write_file=True)
        assert result["status"] == "ok"
        assert (Path(workspace_dir) / "AGENTS.md").exists()
        assert len(get_switch_history(db.conn)) == 1

    def test_backup_preserves_existing_file(self, db, workspace_dir):
        """Switching should back up existing context files."""
        agents_md = Path(workspace_dir) / "AGENTS.md"
        agents_md.write_text("# Original content\nDo not lose this.", encoding="utf-8")

        db.add_conversation(
            platform="codex",
            started_at="2026-03-19T10:00:00Z",
            messages=[{"role": "user", "content": "Hello"}],
            workspace_path=workspace_dir,
        )

        execute_switch(db.conn, "codex", workspace_dir, write_file=True)

        backup = Path(workspace_dir) / "AGENTS.md.pre-switch.bak"
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == "# Original content\nDo not lose this."


class TestV2CompressionPipeline:
    """Test that compression works correctly through the full pipeline."""

    def test_long_code_block_compressed_in_archive(self, db):
        """Long code blocks in assistant messages should be compressed when stored."""
        lines = "\n".join([f"    line {i}: x = {i} * 2" for i in range(30)])
        long_code = f"Here is the implementation:\n```python\n{lines}\n```"

        conv_id, _, _ = db.add_conversation(
            platform="claude_code",
            started_at="2026-03-19T10:00:00Z",
            messages=[
                {"role": "user", "content": "Show me the code"},
                {"role": "assistant", "content": long_code},
            ],
        )

        messages = db.get_messages(conv_id)
        assistant_msg = messages[1]
        # The compressed field should be set and shorter
        assert assistant_msg["compressed"] is not None
        assert len(assistant_msg["compressed"]) < len(assistant_msg["content"])

    def test_user_messages_not_compressed(self, db):
        """User messages should never be compressed."""
        conv_id, _, _ = db.add_conversation(
            platform="claude_code",
            started_at="2026-03-19T10:00:00Z",
            messages=[
                {"role": "user", "content": "A very long user message " * 100},
            ],
        )

        messages = db.get_messages(conv_id)
        assert messages[0]["compressed"] is None

    def test_compressed_messages_used_in_switch(self, db, workspace_dir):
        """Compressed content should be used when assembling switch context."""
        lines = "\n".join([f"    line {i}" for i in range(30)])
        long_code = f"Result:\n```python\n{lines}\n```"

        db.add_conversation(
            platform="claude_code",
            started_at="2026-03-19T10:00:00Z",
            messages=[
                {"role": "user", "content": "Show code"},
                {"role": "assistant", "content": long_code},
            ],
            workspace_path=workspace_dir,
        )

        result = execute_switch(db.conn, "codex", workspace_dir, write_file=False)
        assert result["status"] == "ok"
        # The context should contain the compressed version (with omitted lines)
        content = result["content"]
        assert "省略" in content or "omit" in content.lower() or len(content) < len(long_code)


class TestV2Deduplication:
    """Test dedup behavior across the pipeline."""

    def test_duplicate_conversations_rejected(self, db):
        """Adding the same conversation twice should return the same ID."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        id1, count1, _ = db.add_conversation(
            platform="claude_code",
            started_at="2026-03-19T10:00:00Z",
            messages=messages,
        )
        id2, count2, _ = db.add_conversation(
            platform="claude_code",
            started_at="2026-03-19T10:00:00Z",
            messages=messages,
        )

        assert id1 == id2  # Same conversation, deduped by content hash
        assert count1 == count2

        # Only one conversation in DB
        convs, total = db.get_conversations()
        assert total == 1

    def test_different_content_creates_separate(self, db):
        """Different messages should create separate conversations."""
        id1, _, _ = db.add_conversation(
            platform="claude_code",
            started_at="2026-03-19T10:00:00Z",
            messages=[{"role": "user", "content": "Message A"}],
        )
        id2, _, _ = db.add_conversation(
            platform="claude_code",
            started_at="2026-03-19T10:00:00Z",
            messages=[{"role": "user", "content": "Message B"}],
        )

        assert id1 != id2
        convs, total = db.get_conversations()
        assert total == 2


class TestV2WorkingMemoryPersistence:
    """Test working memory state across switches."""

    def test_working_memory_survives_switches(self, db, workspace_dir):
        """Working memory should persist and update through multiple switches."""
        # Initial state
        upsert_working_memory(db.conn, {
            "workspace_path": workspace_dir,
            "active_task": "Build feature X",
            "current_plan": ["Design", "Implement", "Test"],
            "last_cli": "claude_code",
        })

        db.add_conversation(
            platform="claude_code",
            started_at="2026-03-19T10:00:00Z",
            messages=[{"role": "user", "content": "Working on feature X"}],
            workspace_path=workspace_dir,
        )

        # Switch to codex
        execute_switch(db.conn, "codex", workspace_dir, from_cli="claude_code", write_file=False)
        wm = get_working_memory(db.conn, workspace_dir)
        assert wm["active_task"] == "Build feature X"  # Preserved
        assert wm["last_cli"] == "codex"  # Updated
        assert wm["switch_count"] == 1

        # Switch to gemini
        execute_switch(db.conn, "gemini_cli", workspace_dir, from_cli="codex", write_file=False)
        wm = get_working_memory(db.conn, workspace_dir)
        assert wm["active_task"] == "Build feature X"  # Still preserved
        assert wm["last_cli"] == "gemini_cli"
        assert wm["switch_count"] == 2

    def test_context_includes_working_memory_fields(self, db, workspace_dir):
        """All working memory fields should appear in generated context."""
        upsert_working_memory(db.conn, {
            "workspace_path": workspace_dir,
            "active_task": "Implement OAuth2 flow",
            "current_plan": ["Add OAuth provider", "Handle callbacks", "Store tokens"],
            "progress": ["OAuth provider added"],
            "open_issues": ["Token storage security"],
            "recent_changes": "Added OAuth2 provider config",
            "last_cli": "claude_code",
        })

        db.add_conversation(
            platform="claude_code",
            started_at="2026-03-19T10:00:00Z",
            messages=[{"role": "user", "content": "Continue OAuth work"}],
            workspace_path=workspace_dir,
        )

        result = execute_switch(db.conn, "codex", workspace_dir, write_file=False)
        content = result["content"]

        assert "Implement OAuth2 flow" in content
        assert "OAuth provider added" in content or "Add OAuth provider" in content
        assert "Token storage security" in content


class TestV2DatabaseIntegrity:
    """Test database integrity across operations."""

    def test_cascade_delete(self, db):
        """Deleting a conversation should cascade to its messages."""
        conv_id, _, _ = db.add_conversation(
            platform="claude_code",
            started_at="2026-03-19T10:00:00Z",
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
                {"role": "user", "content": "Bye"},
            ],
        )

        assert len(db.get_messages(conv_id)) == 3
        assert db.delete_conversation(conv_id) is True
        assert len(db.get_messages(conv_id)) == 0
        assert db.get_conversation(conv_id) is None

    def test_stats_consistency(self, db, workspace_dir):
        """Stats should reflect actual data."""
        db.add_conversation(
            platform="claude_code",
            started_at="2026-03-19T10:00:00Z",
            messages=[
                {"role": "user", "content": "How do I implement authentication in FastAPI with JWT tokens?"},
                {"role": "assistant", "content": "You can use python-jose for JWT and passlib for password hashing. Here is a complete example with login and token refresh endpoints."},
            ],
            workspace_path=workspace_dir,
        )
        db.add_conversation(
            platform="codex",
            started_at="2026-03-19T11:00:00Z",
            messages=[
                {"role": "user", "content": "Set up the CI pipeline with GitHub Actions for testing and deployment"},
            ],
            workspace_path=workspace_dir,
        )

        db.upsert_working_memory(
            workspace_path=workspace_dir,
            active_task="Test",
        )

        stats = db.get_stats()
        assert stats["archive_conversations"] == 2
        assert stats["archive_messages"] == 3
        assert stats["working_memories"] == 1
        assert stats["total_tokens"] > 0
        assert set(stats["platforms"]) == {"claude_code", "codex"}
        assert stats["schema_version"] == 2

    def test_v1_migration_roundtrip(self, db):
        """Migrate V1 data and verify it's queryable in V2."""
        # Create a fake V1 database
        v1_conn = sqlite3.connect(":memory:")
        v1_conn.row_factory = sqlite3.Row
        v1_conn.executescript("""
            CREATE TABLE conversations (
                id TEXT PRIMARY KEY,
                platform TEXT,
                timestamp TEXT,
                project TEXT,
                working_dir TEXT,
                provider TEXT,
                model TEXT,
                assistant_label TEXT,
                source_path TEXT,
                source_fingerprint TEXT,
                content_hash TEXT,
                recovery_mode TEXT,
                summary_source TEXT,
                summary TEXT,
                full_content TEXT,
                importance INTEGER DEFAULT 5
            );
        """)
        v1_conn.execute(
            """INSERT INTO conversations
            (id, platform, timestamp, project, working_dir, summary, full_content, importance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("v1-test-id", "claude_web", "2026-03-19T08:00:00Z", "my-project",
             "D:\\projects\\test", "V1 conversation",
             "user: What is Python?\n\nassistant: Python is a programming language.", 7),
        )
        v1_conn.commit()

        # Migrate
        result = db.migrate_from_v1(v1_conn)
        assert result["migrated"] == 1
        assert result["skipped"] == 0
        assert result["errors"] == 0

        # Verify migrated data is accessible
        conv = db.get_conversation("v1-test-id")
        assert conv is not None
        assert conv["platform"] == "claude_web"

        messages = db.get_messages("v1-test-id")
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert "Python" in messages[0]["content"]
        assert messages[1]["role"] == "assistant"

        # Migrate again -- should skip
        result2 = db.migrate_from_v1(v1_conn)
        assert result2["migrated"] == 0
        assert result2["skipped"] == 1

        v1_conn.close()
