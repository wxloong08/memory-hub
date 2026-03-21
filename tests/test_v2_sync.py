"""
Tests for V2 sync engine modules:
1. database_v2.py  - Archive conversations/messages CRUD, working memory, V1→V2 migration
2. message_compressor.py - Tool-use compression, code blocks, error stacks, thinking blocks
3. sync_scheduler.py - Incremental sync logic, dedup, SyncState
4. api_v2.py - V2 endpoint integration tests (TestClient)
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from message_compressor import (
    compress_message,
    compress_messages,
    compression_ratio,
    estimate_tokens,
    _compress_code_blocks,
    _compress_error_stacks,
    _compress_thinking_blocks,
    _compress_tool_blocks,
    _compress_tool_read,
    _compress_tool_bash,
    _compress_tool_edit,
    _compress_tool_search,
    _compress_tool_write,
    _compress_tool_websearch,
    _compress_tool_agent,
)
from database_v2 import DatabaseV2
from sync_scheduler import SyncState, _infer_source_from_path


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def db_v2(tmp_path):
    """Create a V2 database instance in a temp directory."""
    db_path = str(tmp_path / "test_v2.db")
    db = DatabaseV2(db_path)
    yield db
    db.conn.close()


@pytest.fixture
def sample_messages():
    """Simple message list for testing."""
    return [
        {"role": "user", "content": "Hello, help me build a web app"},
        {"role": "assistant", "content": "Sure! Let's start with the architecture."},
        {"role": "user", "content": "What framework should I use?"},
        {"role": "assistant", "content": "I recommend FastAPI for the backend."},
    ]


@pytest.fixture
def populated_db_v2(db_v2, sample_messages):
    """Database with some conversations pre-populated."""
    for i in range(5):
        db_v2.add_conversation(
            platform=["codex", "claude_code", "gemini_cli", "antigravity", "codex"][i],
            started_at=(datetime.now() - timedelta(hours=i)).isoformat(),
            messages=[
                {"role": "user", "content": f"Question {i} about topic"},
                {"role": "assistant", "content": f"Answer {i} with details"},
            ],
            workspace_path=f"/projects/project-{i % 2}",
            provider="openai" if i % 2 == 0 else "anthropic",
            model="gpt-5" if i % 2 == 0 else "claude-sonnet",
            summary=f"Summary {i}",
        )
    return db_v2


# ===================================================================
# 1. database_v2.py tests
# ===================================================================

class TestDatabaseV2Schema:
    """Test V2 schema creation."""

    def test_tables_created(self, db_v2):
        tables = db_v2.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "archive_conversations" in table_names
        assert "archive_messages" in table_names
        assert "working_memory" in table_names
        assert "schema_version" in table_names

    def test_schema_version_recorded(self, db_v2):
        row = db_v2.conn.execute(
            "SELECT version FROM schema_version WHERE version = 2"
        ).fetchone()
        assert row is not None
        assert row[0] == 2

    def test_wal_mode_enabled(self, db_v2):
        mode = db_v2.conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

    def test_foreign_keys_enabled(self, db_v2):
        fk = db_v2.conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1


class TestArchiveConversationsCRUD:
    """Test archive_conversations and archive_messages CRUD."""

    def test_add_conversation_basic(self, db_v2, sample_messages):
        conv_id, msg_count, tokens = db_v2.add_conversation(
            platform="codex",
            started_at=datetime.now().isoformat(),
            messages=sample_messages,
        )
        assert conv_id is not None
        assert msg_count == 4
        assert tokens > 0

    def test_add_conversation_with_all_fields(self, db_v2, sample_messages):
        conv_id, msg_count, tokens = db_v2.add_conversation(
            platform="claude_code",
            started_at=datetime.now().isoformat(),
            messages=sample_messages,
            session_id="session-123",
            workspace_path="/projects/test",
            ended_at=datetime.now().isoformat(),
            summary="Test summary",
            summary_source="ai",
            importance=8,
            provider="anthropic",
            model="claude-sonnet",
            assistant_label="Claude Code",
            source_path="/path/to/file.jsonl",
            source_fingerprint="123:456",
            content_hash="custom_hash_123",
            metadata={"key": "value"},
        )
        conv = db_v2.get_conversation(conv_id)
        assert conv["platform"] == "claude_code"
        assert conv["session_id"] == "session-123"
        assert conv["workspace_path"] == "/projects/test"
        assert conv["summary"] == "Test summary"
        assert conv["importance"] == 8
        assert conv["provider"] == "anthropic"
        assert conv["model"] == "claude-sonnet"
        assert conv["source_fingerprint"] == "123:456"
        assert conv["content_hash"] == "custom_hash_123"

    def test_add_conversation_auto_content_hash(self, db_v2, sample_messages):
        conv_id, _, _ = db_v2.add_conversation(
            platform="codex",
            started_at=datetime.now().isoformat(),
            messages=sample_messages,
        )
        conv = db_v2.get_conversation(conv_id)
        assert conv["content_hash"] is not None
        assert len(conv["content_hash"]) == 64  # SHA-256 hex

    def test_add_conversation_dedup_by_content_hash(self, db_v2, sample_messages):
        now = datetime.now().isoformat()
        id1, _, _ = db_v2.add_conversation(
            platform="codex", started_at=now, messages=sample_messages,
        )
        id2, _, _ = db_v2.add_conversation(
            platform="codex", started_at=now, messages=sample_messages,
        )
        assert id1 == id2

    def test_add_conversation_dedup_by_source_fingerprint(self, db_v2, sample_messages):
        now = datetime.now().isoformat()
        id1, _, _ = db_v2.add_conversation(
            platform="codex", started_at=now, messages=sample_messages,
            source_path="/file.jsonl", source_fingerprint="100:200",
        )
        id2, _, _ = db_v2.add_conversation(
            platform="codex", started_at=now,
            messages=[{"role": "user", "content": "different"}],
            source_path="/file.jsonl", source_fingerprint="100:200",
        )
        assert id1 == id2

    def test_messages_stored_correctly(self, db_v2, sample_messages):
        conv_id, _, _ = db_v2.add_conversation(
            platform="codex",
            started_at=datetime.now().isoformat(),
            messages=sample_messages,
        )
        msgs = db_v2.get_messages(conv_id)
        assert len(msgs) == 4
        assert msgs[0]["role"] == "user"
        assert msgs[0]["ordinal"] == 0
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["ordinal"] == 1

    def test_messages_cascade_delete(self, db_v2, sample_messages):
        conv_id, _, _ = db_v2.add_conversation(
            platform="codex",
            started_at=datetime.now().isoformat(),
            messages=sample_messages,
        )
        db_v2.delete_conversation(conv_id)
        msgs = db_v2.get_messages(conv_id)
        assert len(msgs) == 0

    def test_delete_nonexistent(self, db_v2):
        assert db_v2.delete_conversation("nonexistent") is False

    def test_get_conversation_not_found(self, db_v2):
        assert db_v2.get_conversation("nonexistent") is None

    def test_get_conversations_pagination(self, populated_db_v2):
        page1, total = populated_db_v2.get_conversations(limit=2, offset=0)
        assert len(page1) == 2
        assert total == 5

        page2, _ = populated_db_v2.get_conversations(limit=2, offset=2)
        assert len(page2) == 2
        assert page1[0]["id"] != page2[0]["id"]

    def test_get_conversations_filter_platform(self, populated_db_v2):
        results, total = populated_db_v2.get_conversations(platform="codex")
        assert all(r["platform"] == "codex" for r in results)
        assert total == 2

    def test_get_conversations_filter_workspace(self, populated_db_v2):
        results, total = populated_db_v2.get_conversations(
            workspace_path="/projects/project-0"
        )
        assert all(r["workspace_path"] == "/projects/project-0" for r in results)

    def test_get_conversations_sort_newest(self, populated_db_v2):
        results, _ = populated_db_v2.get_conversations(sort="newest", limit=5)
        timestamps = [r["started_at"] for r in results]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_get_conversations_sort_oldest(self, populated_db_v2):
        results, _ = populated_db_v2.get_conversations(sort="oldest", limit=5)
        timestamps = [r["started_at"] for r in results]
        assert timestamps == sorted(timestamps)

    def test_get_recent_conversations(self, populated_db_v2):
        results = populated_db_v2.get_recent_conversations(limit=3)
        assert len(results) == 3

    def test_get_recent_conversations_by_workspace(self, populated_db_v2):
        results = populated_db_v2.get_recent_conversations(
            workspace_path="/projects/project-0", limit=10
        )
        assert all(r["workspace_path"] == "/projects/project-0" for r in results)

    def test_update_conversation_summary(self, db_v2, sample_messages):
        conv_id, _, _ = db_v2.add_conversation(
            platform="codex",
            started_at=datetime.now().isoformat(),
            messages=sample_messages,
        )
        result = db_v2.update_conversation_summary(conv_id, "New summary", "ai")
        assert result is True
        conv = db_v2.get_conversation(conv_id)
        assert conv["summary"] == "New summary"
        assert conv["summary_source"] == "ai"

    def test_update_summary_nonexistent(self, db_v2):
        assert db_v2.update_conversation_summary("nonexistent", "x") is False


class TestArchiveMessages:
    """Test message-level queries."""

    def test_get_messages_with_role_filter(self, db_v2, sample_messages):
        conv_id, _, _ = db_v2.add_conversation(
            platform="codex",
            started_at=datetime.now().isoformat(),
            messages=sample_messages,
        )
        user_msgs = db_v2.get_messages(conv_id, roles=["user"])
        assert len(user_msgs) == 2
        assert all(m["role"] == "user" for m in user_msgs)

    def test_get_messages_with_limit(self, db_v2, sample_messages):
        conv_id, _, _ = db_v2.add_conversation(
            platform="codex",
            started_at=datetime.now().isoformat(),
            messages=sample_messages,
        )
        msgs = db_v2.get_messages(conv_id, limit=2)
        assert len(msgs) == 2

    def test_get_compressed_messages(self, db_v2):
        """Compressed field should be preferred when available."""
        messages = [
            {"role": "user", "content": "Do something"},
            {"role": "assistant", "content": "Tool: Read\n```json\n{\"path\": \"/foo/bar.py\"}\n```\nHere is the content of the file."},
        ]
        conv_id, _, _ = db_v2.add_conversation(
            platform="codex",
            started_at=datetime.now().isoformat(),
            messages=messages,
        )
        compressed = db_v2.get_compressed_messages(conv_id)
        # The assistant message should show the compressed version
        assistant_msg = [m for m in compressed if m["role"] == "assistant"][0]
        assert "读取文件" in assistant_msg["content"] or len(assistant_msg["content"]) <= len(messages[1]["content"])

    def test_reconstruct_full_content(self, db_v2, sample_messages):
        conv_id, _, _ = db_v2.add_conversation(
            platform="codex",
            started_at=datetime.now().isoformat(),
            messages=sample_messages,
        )
        full = db_v2.reconstruct_full_content(conv_id)
        assert "user:" in full
        assert "assistant:" in full
        assert "Hello" in full


class TestFindExistingConversation:
    """Test dedup logic."""

    def test_find_by_source_fingerprint(self, db_v2, sample_messages):
        conv_id, _, _ = db_v2.add_conversation(
            platform="codex",
            started_at=datetime.now().isoformat(),
            messages=sample_messages,
            source_path="/session.jsonl",
            source_fingerprint="999:888",
        )
        found = db_v2.find_existing_conversation(
            platform="codex",
            source_path="/session.jsonl",
            source_fingerprint="999:888",
        )
        assert found == conv_id

    def test_find_by_content_hash(self, db_v2, sample_messages):
        conv_id, _, _ = db_v2.add_conversation(
            platform="codex",
            started_at=datetime.now().isoformat(),
            messages=sample_messages,
            content_hash="test_hash_abc",
        )
        found = db_v2.find_existing_conversation(
            platform="codex",
            content_hash="test_hash_abc",
        )
        assert found == conv_id

    def test_not_found(self, db_v2):
        found = db_v2.find_existing_conversation(
            platform="codex",
            content_hash="nonexistent",
        )
        assert found is None

    def test_fingerprint_priority_over_content_hash(self, db_v2, sample_messages):
        """Source fingerprint match should be checked first."""
        conv_id, _, _ = db_v2.add_conversation(
            platform="codex",
            started_at=datetime.now().isoformat(),
            messages=sample_messages,
            source_path="/session.jsonl",
            source_fingerprint="111:222",
            content_hash="hash_xyz",
        )
        found = db_v2.find_existing_conversation(
            platform="codex",
            source_path="/session.jsonl",
            source_fingerprint="111:222",
            content_hash="different_hash",
        )
        assert found == conv_id


class TestWorkingMemory:
    """Test working memory CRUD."""

    def test_upsert_creates_new(self, db_v2):
        result = db_v2.upsert_working_memory(
            "/projects/test",
            active_task="Build feature X",
            current_plan=["Step 1", "Step 2"],
            last_cli="claude_code",
        )
        assert result["workspace_path"] == "/projects/test"
        assert result["active_task"] == "Build feature X"
        assert result["current_plan"] == ["Step 1", "Step 2"]

    def test_upsert_updates_existing(self, db_v2):
        db_v2.upsert_working_memory("/projects/test", active_task="Task 1")
        db_v2.upsert_working_memory("/projects/test", active_task="Task 2")
        result = db_v2.get_working_memory("/projects/test")
        assert result["active_task"] == "Task 2"

    def test_upsert_merge_semantics(self, db_v2):
        """Only provided fields should be updated."""
        db_v2.upsert_working_memory(
            "/projects/test",
            active_task="Task 1",
            current_plan=["A", "B"],
        )
        db_v2.upsert_working_memory(
            "/projects/test",
            active_task="Task 2",
            # current_plan not provided — should keep old value
        )
        result = db_v2.get_working_memory("/projects/test")
        assert result["active_task"] == "Task 2"
        assert result["current_plan"] == ["A", "B"]

    def test_get_working_memory_not_found(self, db_v2):
        assert db_v2.get_working_memory("/nonexistent") is None

    def test_delete_working_memory(self, db_v2):
        db_v2.upsert_working_memory("/projects/test", active_task="x")
        assert db_v2.delete_working_memory("/projects/test") is True
        assert db_v2.get_working_memory("/projects/test") is None

    def test_delete_nonexistent_working_memory(self, db_v2):
        assert db_v2.delete_working_memory("/nonexistent") is False

    def test_increment_switch_count(self, db_v2):
        db_v2.upsert_working_memory("/projects/test", active_task="x")
        count1 = db_v2.increment_switch_count("/projects/test")
        assert count1 == 1
        count2 = db_v2.increment_switch_count("/projects/test")
        assert count2 == 2

    def test_increment_nonexistent_returns_zero(self, db_v2):
        assert db_v2.increment_switch_count("/nonexistent") == 0

    def test_list_working_memories(self, db_v2):
        db_v2.upsert_working_memory("/projects/a", active_task="Task A")
        db_v2.upsert_working_memory("/projects/b", active_task="Task B")
        results = db_v2.list_working_memories()
        assert len(results) == 2
        paths = [r["workspace_path"] for r in results]
        assert "/projects/a" in paths
        assert "/projects/b" in paths


class TestV1Migration:
    """Test V1 -> V2 data migration."""

    def _create_v1_db(self, db_path):
        """Create a mock V1 database."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("""
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
            )
        """)
        return conn

    def test_migrate_basic(self, db_v2, tmp_path):
        v1_path = str(tmp_path / "v1.db")
        v1_conn = self._create_v1_db(v1_path)
        v1_conn.execute(
            """INSERT INTO conversations
            (id, platform, timestamp, full_content, importance, summary)
            VALUES (?, ?, ?, ?, ?, ?)""",
            ("conv-1", "codex", datetime.now().isoformat(),
             "user: Hello\nassistant: Hi there", 7, "Test conv"),
        )
        v1_conn.commit()

        result = db_v2.migrate_from_v1(v1_conn)
        v1_conn.close()

        assert result["migrated"] == 1
        assert result["skipped"] == 0
        assert result["errors"] == 0

        # Verify data in V2
        conv = db_v2.get_conversation("conv-1")
        assert conv is not None
        assert conv["platform"] == "codex"
        msgs = db_v2.get_messages("conv-1")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hello"

    def test_migrate_skips_existing(self, db_v2, tmp_path):
        v1_path = str(tmp_path / "v1.db")
        v1_conn = self._create_v1_db(v1_path)
        v1_conn.execute(
            """INSERT INTO conversations
            (id, platform, timestamp, full_content) VALUES (?, ?, ?, ?)""",
            ("conv-1", "codex", datetime.now().isoformat(), "user: Hello"),
        )
        v1_conn.commit()

        # First migration
        db_v2.migrate_from_v1(v1_conn)
        # Second migration should skip
        result = db_v2.migrate_from_v1(v1_conn)
        v1_conn.close()

        assert result["migrated"] == 0
        assert result["skipped"] == 1

    def test_migrate_preserves_metadata(self, db_v2, tmp_path):
        v1_path = str(tmp_path / "v1.db")
        v1_conn = self._create_v1_db(v1_path)
        v1_conn.execute(
            """INSERT INTO conversations
            (id, platform, timestamp, full_content, project, recovery_mode, provider, model)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("conv-1", "antigravity", datetime.now().isoformat(),
             "user: Test", "my-project", "live-rpc", "anthropic", "claude-sonnet"),
        )
        v1_conn.commit()

        db_v2.migrate_from_v1(v1_conn)
        v1_conn.close()

        conv = db_v2.get_conversation("conv-1")
        assert conv["platform"] == "antigravity"
        assert conv["provider"] == "anthropic"
        assert conv["model"] == "claude-sonnet"
        meta = json.loads(conv["metadata"])
        assert meta["recovery_mode"] == "live-rpc"
        assert meta["project"] == "my-project"


class TestParseV1FullContent:
    """Test the V1 content parser."""

    def test_basic_parse(self):
        text = "user: Hello\nassistant: Hi there"
        result = DatabaseV2._parse_v1_full_content(text)
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Hello"}
        assert result[1] == {"role": "assistant", "content": "Hi there"}

    def test_multiline_content(self):
        text = "user: Hello\nHow are you?\nassistant: I'm fine\nThanks"
        result = DatabaseV2._parse_v1_full_content(text)
        assert len(result) == 2
        assert "How are you?" in result[0]["content"]
        assert "Thanks" in result[1]["content"]

    def test_empty_content(self):
        result = DatabaseV2._parse_v1_full_content("")
        assert result == []

    def test_no_role_prefix(self):
        result = DatabaseV2._parse_v1_full_content("just some random text")
        assert result == []


class TestDatabaseV2Stats:
    """Test stats method."""

    def test_empty_stats(self, db_v2):
        stats = db_v2.get_stats()
        assert stats["archive_conversations"] == 0
        assert stats["archive_messages"] == 0
        assert stats["working_memories"] == 0
        assert stats["schema_version"] == 2

    def test_stats_after_data(self, populated_db_v2):
        stats = populated_db_v2.get_stats()
        assert stats["archive_conversations"] == 5
        assert stats["archive_messages"] == 10  # 2 msgs per conv
        assert stats["total_tokens"] > 0
        assert "codex" in stats["platforms"]


# ===================================================================
# 2. message_compressor.py tests
# ===================================================================

class TestToolCompressors:
    """Test individual tool compressors."""

    def test_compress_tool_read(self):
        block = 'path: "/foo/bar.py"\nline 1\nline 2\nline 3'
        result = _compress_tool_read(block)
        assert "读取文件" in result
        assert "/foo/bar.py" in result
        assert "行" in result

    def test_compress_tool_bash(self):
        block = 'command: "ls -la"\nexit_code: 0\noutput'
        result = _compress_tool_bash(block)
        assert "执行" in result
        assert "ls -la" in result
        assert "成功" in result

    def test_compress_tool_bash_failure(self):
        block = 'command: "make build"\nexit_code: 1\nerror output'
        result = _compress_tool_bash(block)
        assert "失败" in result

    def test_compress_tool_edit(self):
        block = 'file: "src/main.py"\nold_string...'
        result = _compress_tool_edit(block)
        assert "编辑" in result
        assert "src/main.py" in result

    def test_compress_tool_search(self):
        block = 'query: "TODO fixme"\n5 matches found'
        result = _compress_tool_search(block)
        assert "搜索" in result
        assert "TODO fixme" in result

    def test_compress_tool_write(self):
        block = 'path: "new_file.py"\ncontent:\nline1\nline2\nline3'
        result = _compress_tool_write(block)
        assert "创建文件" in result
        assert "new_file.py" in result

    def test_compress_tool_websearch(self):
        block = 'query: "python asyncio tutorial"'
        result = _compress_tool_websearch(block)
        assert "网络搜索" in result
        assert "python asyncio" in result

    def test_compress_tool_agent(self):
        block = 'task: "Analyze the codebase"'
        result = _compress_tool_agent(block)
        assert "子代理" in result
        assert "Analyze" in result


class TestToolBlockCompression:
    """Test tool block detection and compression."""

    def test_compress_tool_use_block(self):
        text = """Some text before
Tool: Read
```json
{"path": "/foo/bar.py"}
```
Some text after"""
        result = _compress_tool_blocks(text)
        assert "读取文件" in result
        assert "Some text before" in result
        assert "Some text after" in result

    def test_unknown_tool_fallback(self):
        text = """Tool: CustomTool
```json
{"data": "value"}
```"""
        result = _compress_tool_blocks(text)
        assert "工具调用" in result
        assert "CustomTool" in result

    def test_no_tool_blocks_unchanged(self):
        text = "Just regular text with no tool blocks."
        result = _compress_tool_blocks(text)
        assert result == text


class TestCodeBlockCompression:
    """Test long code block compression."""

    def test_short_code_block_unchanged(self):
        code = "```python\nprint('hello')\nprint('world')\n```"
        result = _compress_code_blocks(code)
        assert result == code

    def test_long_code_block_compressed(self):
        lines = [f"line {i}" for i in range(30)]
        code = "```python\n" + "\n".join(lines) + "\n```"
        result = _compress_code_blocks(code)
        assert "省略" in result
        assert "line 0" in result  # Head preserved
        assert "line 29" in result  # Tail preserved

    def test_preserves_language_tag(self):
        lines = [f"x = {i}" for i in range(25)]
        code = "```javascript\n" + "\n".join(lines) + "\n```"
        result = _compress_code_blocks(code)
        assert "```javascript" in result


class TestErrorStackCompression:
    """Test error stack trace compression."""

    def test_short_traceback_unchanged(self):
        trace = "Traceback (most recent call last):\n  File 'a.py'\nValueError: bad"
        result = _compress_error_stacks(trace)
        assert "Traceback" in result
        assert "ValueError" in result

    def test_long_traceback_compressed(self):
        lines = ["Traceback (most recent call last):"]
        for i in range(15):
            lines.append(f"  File 'module_{i}.py', line {i}")
        lines.append("RuntimeError: something broke")
        trace = "\n".join(lines)
        result = _compress_error_stacks(trace)
        assert "堆栈省略" in result

    def test_generic_stack_compressed(self):
        lines = []
        for i in range(12):
            lines.append(f"    at Module.func{i} (file{i}.js:{i}:0)")
        stack = "\n".join(lines)
        result = _compress_error_stacks(stack)
        assert "堆栈省略" in result


class TestThinkingBlockCompression:
    """Test thinking block compression."""

    def test_thinking_block_removed(self):
        text = """Before thinking.
<details>
<summary>Full Thinking</summary>
This is a very long internal thought process that the model went through
to arrive at the answer. It contains many details and reasoning steps.
</details>
After thinking."""
        result = _compress_thinking_blocks(text)
        assert "思考过程已省略" in result
        assert "very long internal" not in result
        assert "Before thinking" in result
        assert "After thinking" in result

    def test_no_thinking_block_unchanged(self):
        text = "No thinking blocks here."
        result = _compress_thinking_blocks(text)
        assert result == text


class TestCompressMessage:
    """Test the main compress_message function."""

    def test_empty_input(self):
        assert compress_message("") == ""
        assert compress_message("   ") == ""

    def test_plain_text_unchanged(self):
        text = "This is a simple answer."
        assert compress_message(text) == text

    def test_all_rules_applied(self):
        text = """Here is the answer.
Tool: Read
```json
{"path": "/foo.py"}
```
```python
""" + "\n".join(f"line {i}" for i in range(25)) + """
```
<details>
<summary>Full Thinking</summary>
Long thought process here.
</details>
Done."""
        result = compress_message(text)
        assert "读取文件" in result
        assert "省略" in result
        assert "思考过程已省略" in result


class TestCompressMessages:
    """Test batch message compression."""

    def test_only_assistant_compressed(self):
        messages = [
            {"role": "user", "content": "Tell me about X"},
            {"role": "assistant", "content": "Tool: Read\n```json\n{\"path\": \"/foo\"}\n```\nAnswer."},
        ]
        result = compress_messages(messages)
        assert result[0]["content"] == "Tell me about X"  # User unchanged
        assert result[1]["role"] == "assistant"

    def test_preserves_user_messages(self):
        messages = [{"role": "user", "content": "Hello"}]
        result = compress_messages(messages)
        assert result[0]["content"] == "Hello"


class TestTokenEstimation:
    """Test token estimation."""

    def test_english_text(self):
        text = "Hello world this is a test"
        tokens = estimate_tokens(text)
        assert tokens > 0
        assert tokens < len(text)  # Should be compressed

    def test_chinese_text(self):
        text = "你好世界这是一个测试"
        tokens = estimate_tokens(text)
        assert tokens > 0

    def test_mixed_text(self):
        text = "Hello 你好 World 世界"
        tokens = estimate_tokens(text)
        assert tokens > 0

    def test_empty_text(self):
        assert estimate_tokens("") == 0
        assert estimate_tokens(None) == 0


class TestCompressionRatio:
    """Test compression ratio calculation."""

    def test_no_compression(self):
        text = "Short text"
        assert compression_ratio(text, text) == 1.0

    def test_full_compression(self):
        original = "A very long text " * 100
        compressed = "Summary"
        ratio = compression_ratio(original, compressed)
        assert ratio < 0.1

    def test_empty_original(self):
        assert compression_ratio("", "anything") == 1.0


# ===================================================================
# 3. sync_scheduler.py tests
# ===================================================================

class TestSyncState:
    """Test SyncState tracking."""

    def test_initial_state(self):
        state = SyncState()
        assert state.running is False
        assert state.last_sync == {}
        assert state.total_synced == {}
        assert state.errors == []

    def test_record_sync(self):
        state = SyncState()
        state.record_sync("codex", 5)
        assert state.total_synced["codex"] == 5
        assert "codex" in state.last_sync

    def test_record_sync_accumulates(self):
        state = SyncState()
        state.record_sync("codex", 3)
        state.record_sync("codex", 2)
        assert state.total_synced["codex"] == 5

    def test_record_error(self):
        state = SyncState()
        state.record_error("codex", "File not found")
        assert len(state.errors) == 1
        assert state.errors[0]["source"] == "codex"
        assert state.errors[0]["error"] == "File not found"

    def test_error_limit(self):
        state = SyncState()
        for i in range(60):
            state.record_error("source", f"error {i}")
        assert len(state.errors) == 50

    def test_to_dict(self):
        state = SyncState()
        state.running = True
        state.record_sync("codex", 3)
        d = state.to_dict()
        assert d["running"] is True
        assert "codex" in d["last_sync"]
        assert d["total_synced"]["codex"] == 3
        assert "recent_errors" in d


class TestInferSourceFromPath:
    """Test source type inference from file paths."""

    def test_codex_path(self):
        from pathlib import Path
        assert _infer_source_from_path(Path("/home/user/.codex/sessions/abc.jsonl")) == "codex"

    def test_claude_code_path(self):
        from pathlib import Path
        assert _infer_source_from_path(Path("/home/user/.claude/projects/abc.jsonl")) == "claude_code"

    def test_antigravity_path(self):
        from pathlib import Path
        assert _infer_source_from_path(Path("/home/user/.antigravity/sessions/abc.pb")) == "antigravity"

    def test_gemini_path(self):
        from pathlib import Path
        assert _infer_source_from_path(Path("/home/user/.gemini/sessions/session-abc.json")) == "gemini_cli"

    def test_unknown_path(self):
        from pathlib import Path
        assert _infer_source_from_path(Path("/random/file.txt")) is None


class TestSyncSourceIncremental:
    """Test incremental sync logic with mocked dependencies."""

    @patch("sync_scheduler.iter_source_items")
    @patch("sync_scheduler.load_state")
    @patch("sync_scheduler.save_state")
    @patch("sync_scheduler.should_skip")
    @patch("sync_scheduler.build_payload")
    @patch("sync_scheduler.mark_imported")
    def test_basic_sync(
        self, mock_mark, mock_build, mock_skip, mock_save, mock_load, mock_iter
    ):
        from sync_scheduler import sync_source_incremental
        from pathlib import Path

        mock_load.return_value = {}
        mock_iter.return_value = [Path("/a.jsonl"), Path("/b.jsonl")]
        mock_skip.return_value = False
        mock_build.side_effect = [
            {"platform": "codex", "messages": [{"role": "user", "content": "hi"}]},
            {"platform": "codex", "messages": [{"role": "user", "content": "bye"}]},
        ]

        callback = MagicMock(side_effect=["id-1", "id-2"])

        result = sync_source_incremental("codex", callback, limit=50)
        assert result["source"] == "codex"
        assert result["scanned"] == 2
        assert result["imported"] == 2
        assert callback.call_count == 2

    @patch("sync_scheduler.iter_source_items")
    @patch("sync_scheduler.load_state")
    @patch("sync_scheduler.save_state")
    @patch("sync_scheduler.should_skip")
    def test_skips_already_imported(
        self, mock_skip, mock_save, mock_load, mock_iter
    ):
        from sync_scheduler import sync_source_incremental
        from pathlib import Path

        mock_load.return_value = {}
        mock_iter.return_value = [Path("/a.jsonl")]
        mock_skip.return_value = True

        callback = MagicMock()
        result = sync_source_incremental("codex", callback, limit=50)
        assert result["imported"] == 0
        assert callback.call_count == 0

    @patch("sync_scheduler.iter_source_items")
    @patch("sync_scheduler.load_state")
    @patch("sync_scheduler.save_state")
    @patch("sync_scheduler.should_skip")
    @patch("sync_scheduler.build_payload")
    def test_respects_limit(
        self, mock_build, mock_skip, mock_save, mock_load, mock_iter
    ):
        from sync_scheduler import sync_source_incremental
        from pathlib import Path

        mock_load.return_value = {}
        mock_iter.return_value = [Path(f"/{i}.jsonl") for i in range(10)]
        mock_skip.return_value = False
        mock_build.return_value = {"platform": "codex", "messages": []}

        callback = MagicMock(return_value="id")
        result = sync_source_incremental("codex", callback, limit=3)
        assert result["scanned"] == 3


# ===================================================================
# 4. api_v2.py integration tests (TestClient)
# ===================================================================

class TestAPIV2Endpoints:
    """Integration tests for V2 API endpoints using FastAPI TestClient."""

    @pytest.fixture(autouse=True)
    def setup_client(self, tmp_path):
        """Create test client with isolated database."""
        # Patch the db_v2 in api_v2 module
        import api_v2
        db_path = str(tmp_path / "api_test.db")
        test_db = DatabaseV2(db_path)
        original_db = api_v2.db_v2
        api_v2.db_v2 = test_db

        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(api_v2.router)
        self.client = TestClient(app)
        self.db = test_db

        yield

        test_db.conn.close()
        api_v2.db_v2 = original_db

    def _make_conversation_payload(self, **overrides):
        base = {
            "platform": "codex",
            "started_at": datetime.now().isoformat(),
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
        }
        base.update(overrides)
        return base

    def test_ingest_conversation(self):
        payload = self._make_conversation_payload()
        resp = self.client.post("/api/v2/conversations", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["message_count"] == 2
        assert data["conversation_id"] is not None

    def test_ingest_with_working_state(self):
        payload = self._make_conversation_payload(
            workspace_path="/projects/test",
            working_state={
                "active_task": "Build feature",
                "plan": ["Step 1", "Step 2"],
            },
        )
        resp = self.client.post("/api/v2/conversations", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["working_memory_updated"] is True

        # Verify working memory was saved
        wm = self.db.get_working_memory("/projects/test")
        assert wm["active_task"] == "Build feature"

    def test_ingest_empty_messages_rejected(self):
        payload = self._make_conversation_payload(messages=[])
        resp = self.client.post("/api/v2/conversations", json=payload)
        assert resp.status_code in (400, 422)  # FastAPI returns 422 for Pydantic validation errors

    def test_list_conversations(self):
        # Add a conversation first
        self.client.post("/api/v2/conversations", json=self._make_conversation_payload())

        resp = self.client.get("/api/v2/conversations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["conversations"]) >= 1

    def test_list_conversations_with_filters(self):
        self.client.post(
            "/api/v2/conversations",
            json=self._make_conversation_payload(platform="claude_code"),
        )
        self.client.post(
            "/api/v2/conversations",
            json=self._make_conversation_payload(
                platform="codex",
                messages=[{"role": "user", "content": "Different content"}],
            ),
        )

        resp = self.client.get("/api/v2/conversations", params={"platform": "claude_code"})
        data = resp.json()
        assert all(c["platform"] == "claude_code" for c in data["conversations"])

    def test_get_conversation_by_id(self):
        post_resp = self.client.post(
            "/api/v2/conversations", json=self._make_conversation_payload()
        )
        conv_id = post_resp.json()["conversation_id"]

        resp = self.client.get(f"/api/v2/conversations/{conv_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == conv_id
        assert "messages" in data

    def test_get_conversation_not_found(self):
        resp = self.client.get("/api/v2/conversations/nonexistent")
        assert resp.status_code == 404

    def test_get_messages(self):
        post_resp = self.client.post(
            "/api/v2/conversations", json=self._make_conversation_payload()
        )
        conv_id = post_resp.json()["conversation_id"]

        resp = self.client.get(f"/api/v2/conversations/{conv_id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) == 2

    def test_get_messages_role_filter(self):
        post_resp = self.client.post(
            "/api/v2/conversations", json=self._make_conversation_payload()
        )
        conv_id = post_resp.json()["conversation_id"]

        resp = self.client.get(
            f"/api/v2/conversations/{conv_id}/messages", params={"role": "user"}
        )
        data = resp.json()
        assert all(m["role"] == "user" for m in data["messages"])

    def test_get_compressed_conversation(self):
        post_resp = self.client.post(
            "/api/v2/conversations", json=self._make_conversation_payload()
        )
        conv_id = post_resp.json()["conversation_id"]

        resp = self.client.get(f"/api/v2/conversations/{conv_id}/compressed")
        assert resp.status_code == 200
        data = resp.json()
        assert "compression_ratio" in data
        assert "messages" in data

    def test_delete_conversation(self):
        post_resp = self.client.post(
            "/api/v2/conversations", json=self._make_conversation_payload()
        )
        conv_id = post_resp.json()["conversation_id"]

        resp = self.client.delete(f"/api/v2/conversations/{conv_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == conv_id

        # Verify deleted
        resp = self.client.get(f"/api/v2/conversations/{conv_id}")
        assert resp.status_code == 404

    def test_delete_nonexistent_conversation(self):
        resp = self.client.delete("/api/v2/conversations/nonexistent")
        assert resp.status_code == 404

    def test_sync_status(self):
        resp = self.client.get("/api/v2/sync/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data
        assert "file_watcher_active" in data

    def test_dedup_via_api(self):
        """Submitting the same conversation twice should return the same ID."""
        payload = self._make_conversation_payload()
        resp1 = self.client.post("/api/v2/conversations", json=payload)
        resp2 = self.client.post("/api/v2/conversations", json=payload)
        assert resp1.json()["conversation_id"] == resp2.json()["conversation_id"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
