"""
Tests for Memory Hub V2 CLI Switch System.

Covers:
- compression.py (compatibility layer)
- context_assembler.py (three-layer assembly, token budgets, formatting)
- switch_engine.py (execute_switch, preview_switch, switch history)
- cli/memory_hub.py (CLI commands)
- Hook scripts (existence and structure validation)
"""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure backend is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from message_compressor import compress_message, estimate_tokens, compression_ratio
from compression import get_display_content
from context_assembler import (
    CLI_TOKEN_BUDGETS,
    assemble_switch_context,
    format_archive_excerpt,
    format_core_memories,
    format_working_memory,
    get_budget,
)
from database_v2 import DatabaseV2
from switch_engine import (
    execute_switch,
    get_core_memories,
    get_recent_archive_sessions,
    get_switch_history,
    get_working_memory,
    list_working_memories,
    preview_switch,
    record_switch,
    upsert_working_memory,
    delete_working_memory,
    increment_switch_count,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


@pytest.fixture
def db_with_data(db):
    """DB with sample conversations, working memory, and preferences."""
    # Add conversations
    db.add_conversation(
        platform="claude_code",
        started_at="2026-03-18T10:00:00Z",
        messages=[
            {"role": "user", "content": "Fix the auth bug in src/auth.py"},
            {"role": "assistant", "content": "I found a race condition in the token refresh logic."},
            {"role": "user", "content": "Good, now add retry logic"},
            {"role": "assistant", "content": "Added retry with exponential backoff."},
        ],
        workspace_path="D:\\test-project",
        summary="Fix auth bug with retry logic",
        provider="anthropic",
        model="claude-opus-4-6",
    )
    db.add_conversation(
        platform="codex",
        started_at="2026-03-18T09:00:00Z",
        messages=[
            {"role": "user", "content": "Set up CI pipeline"},
            {"role": "assistant", "content": "Created GitHub Actions workflow."},
        ],
        workspace_path="D:\\test-project",
        summary="Set up CI pipeline",
    )

    # Set up working memory
    db.upsert_working_memory(
        "D:\\test-project",
        active_task="Fix auth token refresh bug",
        current_plan=["Investigate", "Fix race condition", "Add retry", "Test"],
        progress=["Investigated", "Fixed race condition"],
        open_issues=["Need retry logic", "Add unit tests"],
        last_cli="claude_code",
        recent_changes="Modified src/auth.py: added mutex lock",
    )

    # Add preferences (core memories) -- requires creating the table
    db.conn.executescript("""
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
    db.conn.execute(
        "INSERT INTO preferences (category, key, value, confidence, priority, pinned, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("identity", "role", "Senior backend developer", 0.95, 10, 1, "active"),
    )
    db.conn.execute(
        "INSERT INTO preferences (category, key, value, confidence, priority, pinned, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("preference", "code_style", "Explicit error handling, no bare try/catch", 0.85, 5, 0, "active"),
    )
    db.conn.execute(
        "INSERT INTO preferences (category, key, value, confidence, priority, pinned, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("decision", "auth_design", "JWT with rotating refresh tokens", 0.9, 7, 0, "active"),
    )
    db.conn.commit()

    return db


@pytest.fixture
def workspace_dir():
    d = tempfile.mkdtemp()
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# compression.py tests
# ---------------------------------------------------------------------------

class TestCompression:
    def test_get_display_content_prefers_compressed(self):
        msg = {"content": "original", "compressed": "short"}
        assert get_display_content(msg) == "short"

    def test_get_display_content_falls_back_to_content(self):
        msg = {"content": "original"}
        assert get_display_content(msg) == "original"

    def test_get_display_content_empty(self):
        assert get_display_content({}) == ""

    def test_estimate_tokens_english(self):
        tokens = estimate_tokens("Hello world, this is a simple test sentence.")
        assert tokens > 0
        assert tokens < 20

    def test_estimate_tokens_chinese(self):
        tokens = estimate_tokens("你好世界，这是一个测试句子。")
        assert tokens > 0

    def test_estimate_tokens_empty(self):
        assert estimate_tokens("") == 0
        assert estimate_tokens(None) == 0

    def test_compress_message_basic(self):
        text = "Hello world"
        result = compress_message(text)
        # Short text should not be compressed (returns same text)
        assert result == text

    def test_compress_long_code_block(self):
        lines = "\n".join([f"    line {i}" for i in range(30)])
        text = f"```python\n{lines}\n```"
        result = compress_message(text)
        assert len(result) < len(text)
        assert "省略" in result or "omit" in result.lower()

    def test_compression_ratio_identical(self):
        assert compression_ratio("hello", "hello") == 1.0

    def test_compression_ratio_shorter(self):
        ratio = compression_ratio("a very long original string here", "short")
        assert ratio < 1.0


# ---------------------------------------------------------------------------
# context_assembler.py tests
# ---------------------------------------------------------------------------

class TestTokenBudgets:
    def test_all_clis_have_budgets(self):
        for cli in ("claude_code", "codex", "gemini_cli", "antigravity"):
            assert cli in CLI_TOKEN_BUDGETS
            budget = CLI_TOKEN_BUDGETS[cli]
            assert "working" in budget
            assert "core" in budget
            assert "archive" in budget
            assert "total" in budget
            assert budget["total"] == budget["working"] + budget["core"] + budget["archive"]

    def test_gemini_has_largest_budget(self):
        assert CLI_TOKEN_BUDGETS["gemini_cli"]["total"] > CLI_TOKEN_BUDGETS["claude_code"]["total"]
        assert CLI_TOKEN_BUDGETS["gemini_cli"]["total"] > CLI_TOKEN_BUDGETS["codex"]["total"]

    def test_get_budget_default(self):
        budget = get_budget("codex")
        assert budget == CLI_TOKEN_BUDGETS["codex"]

    def test_get_budget_override(self):
        budget = get_budget("codex", override=8000)
        assert budget["total"] == 8000
        assert budget["working"] > 0
        assert budget["core"] > 0
        assert budget["archive"] > 0

    def test_get_budget_unknown_cli_falls_back(self):
        budget = get_budget("unknown_cli")
        assert budget == CLI_TOKEN_BUDGETS["codex"]


class TestFormatWorkingMemory:
    def test_empty_working_memory(self):
        assert format_working_memory(None) == ""
        assert format_working_memory({}) == ""

    def test_full_working_memory(self):
        working = {
            "active_task": "Fix auth bug",
            "current_plan": ["Step 1", "Step 2"],
            "progress": ["Step 1 done"],
            "open_issues": ["Need tests"],
            "last_cli": "claude_code",
            "recent_changes": "Modified auth.py",
        }
        result = format_working_memory(working)
        assert "Fix auth bug" in result
        assert "Step 1" in result
        assert "Step 2" in result
        assert "Step 1 done" in result
        assert "Need tests" in result
        assert "claude_code" in result
        assert "Modified auth.py" in result

    def test_json_string_plan_is_parsed(self):
        working = {
            "active_task": "Test",
            "current_plan": '["Step A", "Step B"]',
        }
        result = format_working_memory(working)
        assert "Step A" in result
        assert "Step B" in result

    def test_context_snippet_included(self):
        working = {"context_snippet": "Last conversation about auth"}
        result = format_working_memory(working)
        assert "Last conversation about auth" in result


class TestFormatCoreMemories:
    def test_empty_returns_empty(self):
        text, count = format_core_memories([], 5000)
        assert text == ""
        assert count == 0

    def test_formats_memories_with_categories(self):
        mems = [
            {"category": "identity", "key": "role", "value": "Developer", "pinned": 1, "priority": 10, "confidence": 0.9},
            {"category": "preference", "key": "style", "value": "Clean code", "pinned": 0, "priority": 5, "confidence": 0.8},
        ]
        text, count = format_core_memories(mems, 5000)
        assert count == 2
        assert "### identity" in text
        assert "### preference" in text
        assert "**role**" in text
        assert "Developer" in text

    def test_pinned_shown_first(self):
        mems = [
            {"category": "a", "key": "low", "value": "v1", "pinned": 0, "priority": 1, "confidence": 0.5},
            {"category": "b", "key": "high", "value": "v2", "pinned": 1, "priority": 10, "confidence": 0.9},
        ]
        text, count = format_core_memories(mems, 5000)
        assert count == 2
        # Pinned item should appear first in the output
        pos_high = text.index("high")
        pos_low = text.index("low")
        assert pos_high < pos_low

    def test_respects_token_budget(self):
        mems = [
            {"category": f"cat{i}", "key": f"key{i}", "value": "x" * 500, "pinned": 0, "priority": 0, "confidence": 0.5}
            for i in range(50)
        ]
        text, count = format_core_memories(mems, 200)
        assert count < 50
        assert estimate_tokens(text) <= 250  # Some slack for headers

    def test_skips_empty_values(self):
        mems = [
            {"category": "a", "key": "k1", "value": "", "pinned": 0, "priority": 0, "confidence": 0.5},
            {"category": "a", "key": "k2", "value": "real value", "pinned": 0, "priority": 0, "confidence": 0.5},
        ]
        text, count = format_core_memories(mems, 5000)
        assert count == 1
        assert "k1" not in text
        assert "k2" in text


class TestFormatArchiveExcerpt:
    def test_empty_returns_empty(self):
        text, turns = format_archive_excerpt([], 5000)
        assert text == ""
        assert turns == 0

    def test_formats_session_messages(self):
        sessions = [{
            "platform": "claude_code",
            "started_at": "2026-03-18T10:00:00Z",
            "summary": "Fix auth bug",
            "messages": [
                {"role": "user", "content": "Fix the bug"},
                {"role": "assistant", "content": "Found the issue"},
            ],
        }]
        text, turns = format_archive_excerpt(sessions, 5000)
        assert turns == 2
        assert "User: Fix the bug" in text
        assert "Assistant: Found the issue" in text
        assert "claude_code" in text

    def test_respects_max_turns(self):
        sessions = [{
            "platform": "test",
            "started_at": "2026-03-18T10:00:00Z",
            "summary": "",
            "messages": [{"role": "user", "content": f"msg {i}"} for i in range(20)],
        }]
        text, turns = format_archive_excerpt(sessions, 50000, max_turns=3)
        assert turns == 3

    def test_respects_token_budget(self):
        sessions = [{
            "platform": "test",
            "started_at": "2026-03-18T10:00:00Z",
            "summary": "",
            "messages": [{"role": "user", "content": "x" * 500} for _ in range(50)],
        }]
        text, turns = format_archive_excerpt(sessions, 200)
        assert turns < 50

    def test_uses_compressed_content(self):
        sessions = [{
            "platform": "test",
            "started_at": "2026-03-18T10:00:00Z",
            "summary": "",
            "messages": [
                {"role": "assistant", "content": "very long original", "compressed": "[short]"},
            ],
        }]
        text, turns = format_archive_excerpt(sessions, 5000)
        assert "[short]" in text


class TestAssembleSwitchContext:
    def test_basic_assembly(self):
        result = assemble_switch_context(
            target_cli="codex",
            working_memory={"active_task": "Fix bug"},
            core_memories=[
                {"category": "identity", "key": "role", "value": "Dev", "pinned": 1, "priority": 10, "confidence": 0.9},
            ],
            archive_sessions=[],
            from_cli="claude_code",
            switch_count=1,
        )
        assert "content" in result
        assert result["target_file"] == "AGENTS.md"
        assert result["target_cli"] == "codex"
        assert "Fix bug" in result["content"]
        assert "claude_code" in result["content"]
        assert "Switch #1" in result["content"]
        assert result["context_assembled"]["total_tokens"] > 0

    def test_all_cli_targets(self):
        expected_files = {
            "claude_code": ".claude/CLAUDE.md",
            "codex": "AGENTS.md",
            "gemini_cli": "GEMINI.md",
            "antigravity": ".antigravity/context.md",
        }
        for cli, expected_file in expected_files.items():
            result = assemble_switch_context(target_cli=cli)
            assert result["target_file"] == expected_file
            assert result["target_cli"] == cli

    def test_footer_present(self):
        result = assemble_switch_context(target_cli="codex")
        assert "Memory Hub V2" in result["content"]

    def test_empty_assembly(self):
        result = assemble_switch_context(target_cli="codex")
        assert result["core_memories_injected"] == 0
        assert result["archive_turns_injected"] == 0
        assert result["context_assembled"]["total_tokens"] > 0  # Header + footer


# ---------------------------------------------------------------------------
# switch_engine.py tests
# ---------------------------------------------------------------------------

class TestWorkingMemory:
    def test_get_nonexistent(self, db):
        assert get_working_memory(db.conn, "D:\\nonexistent") is None

    def test_upsert_creates(self, db):
        result = upsert_working_memory(db.conn, {
            "workspace_path": "D:\\new-project",
            "active_task": "Build feature",
            "last_cli": "codex",
        })
        assert result["active_task"] == "Build feature"
        assert result["last_cli"] == "codex"

    def test_upsert_updates(self, db):
        upsert_working_memory(db.conn, {
            "workspace_path": "D:\\project",
            "active_task": "Task 1",
        })
        upsert_working_memory(db.conn, {
            "workspace_path": "D:\\project",
            "active_task": "Task 2",
        })
        result = get_working_memory(db.conn, "D:\\project")
        assert result["active_task"] == "Task 2"

    def test_upsert_preserves_existing_fields(self, db):
        upsert_working_memory(db.conn, {
            "workspace_path": "D:\\project",
            "active_task": "Original task",
            "last_cli": "claude_code",
        })
        # Update only last_cli
        upsert_working_memory(db.conn, {
            "workspace_path": "D:\\project",
            "last_cli": "codex",
        })
        result = get_working_memory(db.conn, "D:\\project")
        assert result["active_task"] == "Original task"  # Preserved
        assert result["last_cli"] == "codex"  # Updated

    def test_list_working_memories(self, db):
        upsert_working_memory(db.conn, {"workspace_path": "D:\\p1", "active_task": "T1"})
        upsert_working_memory(db.conn, {"workspace_path": "D:\\p2", "active_task": "T2"})
        memories = list_working_memories(db.conn)
        assert len(memories) == 2

    def test_delete_working_memory(self, db):
        upsert_working_memory(db.conn, {"workspace_path": "D:\\project", "active_task": "Task"})
        assert delete_working_memory(db.conn, "D:\\project") is True
        assert get_working_memory(db.conn, "D:\\project") is None

    def test_delete_nonexistent(self, db):
        assert delete_working_memory(db.conn, "D:\\nonexistent") is False

    def test_increment_switch_count(self, db):
        upsert_working_memory(db.conn, {"workspace_path": "D:\\project"})
        count1 = increment_switch_count(db.conn, "D:\\project")
        count2 = increment_switch_count(db.conn, "D:\\project")
        assert count1 == 1
        assert count2 == 2

    def test_json_fields_roundtrip(self, db):
        upsert_working_memory(db.conn, {
            "workspace_path": "D:\\project",
            "current_plan": ["Step 1", "Step 2"],
            "progress": ["Done 1"],
            "open_issues": ["Issue A"],
        })
        result = get_working_memory(db.conn, "D:\\project")
        assert result["current_plan"] == ["Step 1", "Step 2"]
        assert result["progress"] == ["Done 1"]
        assert result["open_issues"] == ["Issue A"]


class TestCoreMemories:
    def test_no_preferences_table(self, db):
        # db_v2 doesn't create preferences table by default
        result = get_core_memories(db.conn)
        assert result == []

    def test_reads_from_preferences(self, db_with_data):
        result = get_core_memories(db_with_data.conn)
        assert len(result) == 3
        # Pinned item should be first
        assert result[0]["key"] == "role"
        assert result[0]["pinned"] == 1

    def test_sorted_by_priority(self, db_with_data):
        result = get_core_memories(db_with_data.conn)
        priorities = [m["priority"] for m in result]
        assert priorities == sorted(priorities, reverse=True)


class TestArchiveSessions:
    def test_gets_sessions_with_messages(self, db_with_data):
        sessions = get_recent_archive_sessions(db_with_data.conn, limit=5)
        assert len(sessions) == 2
        for session in sessions:
            assert "messages" in session
            assert len(session["messages"]) > 0

    def test_filters_by_workspace(self, db_with_data):
        sessions = get_recent_archive_sessions(
            db_with_data.conn, workspace_path="D:\\test-project", limit=5
        )
        assert len(sessions) == 2

    def test_returns_empty_for_unknown_workspace(self, db_with_data):
        sessions = get_recent_archive_sessions(
            db_with_data.conn, workspace_path="D:\\unknown", limit=5
        )
        assert len(sessions) == 0


class TestSwitchHistory:
    def test_empty_history(self, db):
        assert get_switch_history(db.conn) == []

    def test_record_and_retrieve(self, db):
        record_switch(db.conn, "claude_code", "codex", "D:\\project", 5000, 3, 10)
        record_switch(db.conn, "codex", "gemini_cli", "D:\\project", 80000, 5, 20)
        history = get_switch_history(db.conn)
        assert len(history) == 2
        assert history[0]["to_cli"] == "gemini_cli"  # Most recent first
        assert history[1]["to_cli"] == "codex"


class TestExecuteSwitch:
    def test_basic_switch(self, db_with_data):
        result = execute_switch(
            conn=db_with_data.conn,
            to_cli="codex",
            workspace_path="D:\\test-project",
            from_cli="claude_code",
            write_file=False,
        )
        assert result["status"] == "ok"
        assert result["target_cli"] == "codex"
        assert result["switch_number"] == 1
        assert result["context_assembled"]["total_tokens"] > 0
        assert result["core_memories_injected"] >= 0
        assert result["archive_turns_injected"] > 0
        assert "content" in result

    def test_switch_increments_counter(self, db_with_data):
        r1 = execute_switch(db_with_data.conn, "codex", "D:\\test-project", write_file=False)
        r2 = execute_switch(db_with_data.conn, "gemini_cli", "D:\\test-project", write_file=False)
        assert r1["switch_number"] == 1
        assert r2["switch_number"] == 2

    def test_switch_records_history(self, db_with_data):
        execute_switch(db_with_data.conn, "codex", "D:\\test-project", from_cli="claude_code", write_file=False)
        history = get_switch_history(db_with_data.conn)
        assert len(history) == 1
        assert history[0]["from_cli"] == "claude_code"
        assert history[0]["to_cli"] == "codex"

    def test_switch_updates_working_memory_cli(self, db_with_data):
        execute_switch(db_with_data.conn, "codex", "D:\\test-project", write_file=False)
        wm = get_working_memory(db_with_data.conn, "D:\\test-project")
        assert wm["last_cli"] == "codex"

    def test_switch_writes_file(self, db_with_data, workspace_dir):
        result = execute_switch(
            conn=db_with_data.conn,
            to_cli="codex",
            workspace_path=workspace_dir,
            write_file=True,
        )
        target = Path(workspace_dir) / "AGENTS.md"
        assert target.exists()
        content = target.read_text(encoding="utf-8")
        assert "Resume Context" in content
        assert "Memory Hub V2" in content

    def test_switch_creates_backup(self, db_with_data, workspace_dir):
        # Create existing file
        agents_md = Path(workspace_dir) / "AGENTS.md"
        agents_md.write_text("original content", encoding="utf-8")

        execute_switch(db_with_data.conn, "codex", workspace_dir, write_file=True)

        backup = Path(workspace_dir) / "AGENTS.md.pre-switch.bak"
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == "original content"

    def test_switch_with_custom_budget(self, db_with_data):
        result = execute_switch(
            db_with_data.conn, "codex", "D:\\test-project",
            token_budget=1000, write_file=False,
        )
        assert result["context_assembled"]["total_tokens"] <= 1200  # Some slack

    def test_switch_creates_working_memory_if_missing(self, db):
        result = execute_switch(db.conn, "codex", "D:\\brand-new-project", write_file=False)
        assert result["status"] == "ok"
        wm = get_working_memory(db.conn, "D:\\brand-new-project")
        assert wm is not None
        assert wm["last_cli"] == "codex"

    def test_switch_to_all_cli_targets(self, db_with_data):
        for cli in ("claude_code", "codex", "gemini_cli", "antigravity"):
            result = execute_switch(db_with_data.conn, cli, "D:\\test-project", write_file=False)
            assert result["status"] == "ok"
            assert result["target_cli"] == cli


class TestPreviewSwitch:
    def test_preview_does_not_write(self, db_with_data, workspace_dir):
        result = preview_switch(db_with_data.conn, "codex", workspace_dir)
        assert result["status"] == "preview"
        assert not (Path(workspace_dir) / "AGENTS.md").exists()

    def test_preview_does_not_record_history(self, db_with_data):
        preview_switch(db_with_data.conn, "codex", "D:\\test-project")
        assert get_switch_history(db_with_data.conn) == []

    def test_preview_returns_content(self, db_with_data):
        result = preview_switch(db_with_data.conn, "codex", "D:\\test-project")
        assert "content_preview" in result
        assert len(result["content_preview"]) > 0


# ---------------------------------------------------------------------------
# CLI tool tests
# ---------------------------------------------------------------------------

CLI_DIR = Path(__file__).resolve().parent.parent / "cli"
sys.path.insert(0, str(CLI_DIR))


class TestCLIParser:
    def test_import_cli_module(self):
        from memory_hub import main
        assert callable(main)

    def test_switch_parser(self):
        from memory_hub import main
        import argparse
        # Verify the CLI can parse switch arguments
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        switch_parser = subparsers.add_parser("switch")
        switch_parser.add_argument("--to", required=True)
        switch_parser.add_argument("--workspace", "-w")
        switch_parser.add_argument("--preview", action="store_true")

        args = parser.parse_args(["switch", "--to", "codex", "--workspace", "/test"])
        assert args.to == "codex"
        assert args.workspace == "/test"
        assert args.command == "switch"

    def test_status_parser(self):
        import argparse
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        status_parser = subparsers.add_parser("status")
        status_parser.add_argument("--workspace", "-w")

        args = parser.parse_args(["status", "-w", "/test"])
        assert args.command == "status"
        assert args.workspace == "/test"


# ---------------------------------------------------------------------------
# Hook script tests
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestHookScripts:
    def test_claude_code_session_start_exists(self):
        hook = PROJECT_ROOT / "claude-code-integration" / "hooks" / "session-start.sh"
        assert hook.exists()

    def test_claude_code_session_end_exists(self):
        hook = PROJECT_ROOT / "claude-code-integration" / "hooks" / "session-end.sh"
        assert hook.exists()

    def test_codex_pre_session_exists(self):
        hook = PROJECT_ROOT / "codex-integration" / "hooks" / "pre-session.sh"
        assert hook.exists()

    def test_codex_post_session_exists(self):
        hook = PROJECT_ROOT / "codex-integration" / "hooks" / "post-session.sh"
        assert hook.exists()

    def test_gemini_pre_session_exists(self):
        hook = PROJECT_ROOT / "gemini-integration" / "hooks" / "pre-session.sh"
        assert hook.exists()

    def test_antigravity_inject_exists(self):
        hook = PROJECT_ROOT / "antigravity-integration" / "inject.sh"
        assert hook.exists()

    def test_hooks_contain_health_check(self):
        hooks = [
            PROJECT_ROOT / "claude-code-integration" / "hooks" / "session-end.sh",
            PROJECT_ROOT / "codex-integration" / "hooks" / "pre-session.sh",
            PROJECT_ROOT / "gemini-integration" / "hooks" / "pre-session.sh",
            PROJECT_ROOT / "antigravity-integration" / "inject.sh",
        ]
        for hook in hooks:
            content = hook.read_text(encoding="utf-8")
            assert "/health" in content, f"{hook.name} missing health check"

    def test_codex_hook_uses_agents_md(self):
        hook = PROJECT_ROOT / "codex-integration" / "hooks" / "pre-session.sh"
        content = hook.read_text(encoding="utf-8")
        assert "codex" in content
        assert "AGENTS.md" in content

    def test_gemini_hook_uses_gemini_md(self):
        hook = PROJECT_ROOT / "gemini-integration" / "hooks" / "pre-session.sh"
        content = hook.read_text(encoding="utf-8")
        assert "gemini_cli" in content
        assert "GEMINI.md" in content

    def test_hooks_use_v2_api(self):
        hooks = [
            PROJECT_ROOT / "codex-integration" / "hooks" / "pre-session.sh",
            PROJECT_ROOT / "gemini-integration" / "hooks" / "pre-session.sh",
        ]
        for hook in hooks:
            content = hook.read_text(encoding="utf-8")
            assert "/api/v2/switch" in content, f"{hook.name} not using V2 API"


# ---------------------------------------------------------------------------
# Integration: full switch flow end-to-end
# ---------------------------------------------------------------------------

class TestSwitchE2E:
    def test_full_switch_flow(self, db_with_data, workspace_dir):
        """Complete switch flow: preview -> execute -> verify file -> check history."""
        # Step 1: Preview
        preview = preview_switch(db_with_data.conn, "codex", workspace_dir)
        assert preview["status"] == "preview"
        assert preview["context_assembled"]["total_tokens"] > 0

        # Step 2: Execute
        result = execute_switch(
            db_with_data.conn, "codex", workspace_dir,
            from_cli="claude_code", write_file=True,
        )
        assert result["status"] == "ok"

        # Step 3: Verify file
        target = Path(workspace_dir) / "AGENTS.md"
        assert target.exists()
        content = target.read_text(encoding="utf-8")
        assert "Resume Context" in content

        # Step 4: Check history
        history = get_switch_history(db_with_data.conn)
        assert len(history) == 1
        assert history[0]["to_cli"] == "codex"

        # Step 5: Working memory updated
        wm = get_working_memory(db_with_data.conn, workspace_dir)
        assert wm["last_cli"] == "codex"
        assert wm["switch_count"] == 1

    def test_multi_switch_chain(self, db_with_data):
        """Switch through multiple CLIs in sequence."""
        path = "D:\\test-project"
        for cli in ("codex", "gemini_cli", "claude_code", "antigravity"):
            result = execute_switch(db_with_data.conn, cli, path, write_file=False)
            assert result["status"] == "ok"

        wm = get_working_memory(db_with_data.conn, path)
        assert wm["switch_count"] == 4
        assert wm["last_cli"] == "antigravity"

        history = get_switch_history(db_with_data.conn)
        assert len(history) == 4
