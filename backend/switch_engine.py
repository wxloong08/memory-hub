"""
Memory Hub V2 -- CLI Switch Orchestration Engine

Coordinates the full switch flow:
1. Capture current state (save working memory)
2. Assemble context from three layers
3. Adapt for target CLI format
4. Inject into target CLI's context file
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from message_compressor import compress_message, estimate_tokens
from context_assembler import assemble_switch_context, get_budget
from database_v2 import DatabaseV2


# ---------------------------------------------------------------------------
# Helper: resolve a DatabaseV2 instance from a connection or instance
# ---------------------------------------------------------------------------

_conn_to_db: dict[int, DatabaseV2] = {}


def _resolve_db(conn_or_db: Union[sqlite3.Connection, DatabaseV2]) -> DatabaseV2:
    """Return a DatabaseV2 instance, creating a lightweight wrapper if needed."""
    if isinstance(conn_or_db, DatabaseV2):
        return conn_or_db
    # Reuse wrapper for the same connection object
    conn_id = id(conn_or_db)
    if conn_id in _conn_to_db:
        return _conn_to_db[conn_id]
    # Build a lightweight wrapper that reuses the existing connection
    db = object.__new__(DatabaseV2)
    db.db_path = ":wrapped:"
    db.conn = conn_or_db
    import threading
    db._lock = threading.RLock()
    _conn_to_db[conn_id] = db
    return db


# ---------------------------------------------------------------------------
# Working memory operations (delegate to DatabaseV2)
# ---------------------------------------------------------------------------

def get_working_memory(conn: Union[sqlite3.Connection, DatabaseV2], workspace_path: str) -> dict | None:
    """Get working memory for a workspace."""
    return _resolve_db(conn).get_working_memory(workspace_path)


def upsert_working_memory(conn: Union[sqlite3.Connection, DatabaseV2], data: dict) -> dict:
    """Create or update working memory for a workspace."""
    db = _resolve_db(conn)
    workspace_path = data["workspace_path"]
    kwargs = {
        k: data[k]
        for k in (
            "active_task", "current_plan", "progress", "open_issues",
            "recent_changes", "last_cli", "last_session_id", "context_snippet",
        )
        if k in data
    }
    return db.upsert_working_memory(workspace_path, **kwargs)


def increment_switch_count(conn: Union[sqlite3.Connection, DatabaseV2], workspace_path: str) -> int:
    """Increment the switch counter for a workspace. Returns new count."""
    return _resolve_db(conn).increment_switch_count(workspace_path)


def delete_working_memory(conn: Union[sqlite3.Connection, DatabaseV2], workspace_path: str) -> bool:
    """Clear working memory for a workspace."""
    return _resolve_db(conn).delete_working_memory(workspace_path)


def list_working_memories(conn: Union[sqlite3.Connection, DatabaseV2]) -> list[dict]:
    """List all active working memories."""
    return _resolve_db(conn).list_working_memories()


# ---------------------------------------------------------------------------
# Core memory retrieval (reads from existing preferences table)
# ---------------------------------------------------------------------------

def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Check if a table exists."""
    cursor = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cursor.fetchone() is not None


def _preferences_has_column(conn: sqlite3.Connection, column: str) -> bool:
    """Check if the preferences table has a given column."""
    if not _table_exists(conn, "preferences"):
        return False
    cursor = conn.execute("PRAGMA table_info(preferences)")
    return column in {row[1] for row in cursor.fetchall()}


def get_core_memories(
    conn: sqlite3.Connection,
    workspace_scope: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Get core memories (from preferences table), optionally filtered by workspace.

    Gracefully handles both V1 (no pinned/workspace_scope columns) and V2 schemas.
    Returns empty list if preferences table doesn't exist.
    """
    if not _table_exists(conn, "preferences"):
        return []

    conn.row_factory = sqlite3.Row

    has_pinned = _preferences_has_column(conn, "pinned")
    has_workspace = _preferences_has_column(conn, "workspace_scope")

    # Build select columns based on available schema
    base_cols = "id, category, key, value, confidence, priority, client_rules, status, last_updated"
    if has_pinned:
        base_cols += ", pinned"
    if has_workspace:
        base_cols += ", workspace_scope"

    query = f"""
        SELECT {base_cols}
        FROM preferences
        WHERE coalesce(status, 'active') = 'active'
    """
    params: list = []

    if workspace_scope and has_workspace:
        query += " AND (workspace_scope IS NULL OR workspace_scope = ?)"
        params.append(workspace_scope)

    if has_pinned:
        query += " ORDER BY CASE WHEN pinned = 1 THEN 0 ELSE 1 END, priority DESC, confidence DESC, last_updated DESC"
    else:
        query += " ORDER BY priority DESC, confidence DESC, last_updated DESC"

    query += " LIMIT ?"
    params.append(limit)

    cursor = conn.execute(query, params)
    results = []
    for row in cursor.fetchall():
        d = dict(row)
        if not has_pinned:
            d["pinned"] = 0
        if isinstance(d.get("client_rules"), str):
            try:
                d["client_rules"] = json.loads(d["client_rules"])
            except (json.JSONDecodeError, TypeError):
                d["client_rules"] = {}
        results.append(d)
    return results


def update_core_memory_access(conn: sqlite3.Connection, memory_ids: list[int]) -> None:
    """Update accessed_at for core memories that were injected."""
    if not memory_ids:
        return
    if not _preferences_has_column(conn, "accessed_at"):
        return
    now = datetime.now().isoformat()
    placeholders = ",".join("?" for _ in memory_ids)
    conn.execute(
        f"UPDATE preferences SET accessed_at = ? WHERE id IN ({placeholders})",
        [now] + list(memory_ids),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Archive retrieval
# ---------------------------------------------------------------------------

def _get_sessions_by_ids(
    conn: sqlite3.Connection,
    conversation_ids: list[str],
) -> list[dict]:
    """Get archive sessions by specific conversation IDs."""
    if not conversation_ids:
        return []
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in conversation_ids)
    try:
        cursor = conn.execute(
            f"SELECT id, platform, started_at, ended_at, summary, provider, model, message_count "
            f"FROM archive_conversations WHERE id IN ({placeholders}) ORDER BY started_at DESC",
            conversation_ids,
        )
        sessions = [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        cursor = conn.execute(
            f"SELECT id, platform, timestamp as started_at, summary, provider, model "
            f"FROM conversations WHERE id IN ({placeholders}) ORDER BY started_at DESC",
            conversation_ids,
        )
        sessions = [dict(row) for row in cursor.fetchall()]
        for s in sessions:
            s["messages"] = []
        return sessions

    for session in sessions:
        msg_cursor = conn.execute(
            "SELECT ordinal, role, content, content_type, compressed, token_estimate, metadata "
            "FROM archive_messages WHERE conversation_id = ? ORDER BY ordinal",
            (session["id"],),
        )
        messages = []
        for msg_row in msg_cursor.fetchall():
            msg = dict(msg_row)
            if isinstance(msg.get("metadata"), str):
                try:
                    msg["metadata"] = json.loads(msg["metadata"])
                except (json.JSONDecodeError, TypeError):
                    msg["metadata"] = {}
            messages.append(msg)
        session["messages"] = messages
    return sessions


def get_recent_archive_sessions(
    conn: sqlite3.Connection,
    workspace_path: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Get recent archive sessions with their compressed messages.

    Returns list of session dicts, each with a 'messages' list.
    """
    conn.row_factory = sqlite3.Row

    # Try V2 archive_conversations table first
    try:
        query = """
            SELECT id, platform, started_at, ended_at, summary, provider, model, message_count
            FROM archive_conversations
        """
        params: list = []
        if workspace_path:
            query += " WHERE workspace_path = ?"
            params.append(workspace_path)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        sessions = [dict(row) for row in cursor.fetchall()]

        # Load messages for each session
        for session in sessions:
            msg_cursor = conn.execute(
                """
                SELECT ordinal, role, content, content_type, compressed, token_estimate, metadata
                FROM archive_messages
                WHERE conversation_id = ?
                ORDER BY ordinal
                """,
                (session["id"],),
            )
            messages = []
            for msg_row in msg_cursor.fetchall():
                msg = dict(msg_row)
                if isinstance(msg.get("metadata"), str):
                    try:
                        msg["metadata"] = json.loads(msg["metadata"])
                    except (json.JSONDecodeError, TypeError):
                        msg["metadata"] = {}
                messages.append(msg)
            session["messages"] = messages

        return sessions

    except sqlite3.OperationalError:
        # Fall back to V1 conversations table
        return _get_recent_sessions_v1(conn, workspace_path, limit)


def _get_recent_sessions_v1(
    conn: sqlite3.Connection,
    workspace_path: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Fallback: get sessions from V1 conversations table."""
    conn.row_factory = sqlite3.Row
    query = """
        SELECT id, platform, timestamp as started_at, summary, provider, model, full_content
        FROM conversations
    """
    params: list = []
    if workspace_path:
        query += " WHERE working_dir = ?"
        params.append(workspace_path)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    cursor = conn.execute(query, params)
    sessions = []
    for row in cursor.fetchall():
        session = dict(row)
        # Parse full_content into messages
        full_content = session.pop("full_content", "") or ""
        messages = _parse_v1_content_to_messages(full_content)
        session["messages"] = messages
        session["message_count"] = len(messages)
        sessions.append(session)
    return sessions


def _parse_v1_content_to_messages(content: str) -> list[dict]:
    """Parse V1 flat text format into message dicts with compression."""
    import re
    lines = content.replace("\r", "").split("\n")
    messages: list[dict] = []
    current: dict | None = None

    for raw_line in lines:
        match = re.match(r"^(user|assistant):\s?(.*)$", raw_line)
        if match:
            if current and str(current.get("content", "")).strip():
                current["content"] = str(current["content"]).strip()
                # Apply compression
                compressed = compress_message(current["content"])
                if compressed != current["content"]:
                    current["compressed"] = compressed
                messages.append(current)
            current = {
                "role": match.group(1),
                "content": match.group(2) or "",
                "content_type": "text",
            }
            continue
        if current is None:
            continue
        current["content"] = f"{current['content']}\n{raw_line}" if current["content"] else raw_line

    if current and str(current.get("content", "")).strip():
        current["content"] = str(current["content"]).strip()
        compressed = compress_message(current["content"])
        if compressed is not None:
            current["compressed"] = compressed
        messages.append(current)

    return messages


# ---------------------------------------------------------------------------
# Switch history
# ---------------------------------------------------------------------------

def record_switch(
    conn: sqlite3.Connection,
    from_cli: str | None,
    to_cli: str,
    workspace_path: str,
    tokens_injected: int,
    core_count: int,
    archive_turns: int,
) -> None:
    """Record a CLI switch event."""
    # Ensure switch_history table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS switch_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_cli TEXT,
            to_cli TEXT NOT NULL,
            workspace_path TEXT NOT NULL,
            tokens_injected INTEGER DEFAULT 0,
            core_memories_count INTEGER DEFAULT 0,
            archive_turns_count INTEGER DEFAULT 0,
            switched_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        """
        INSERT INTO switch_history (from_cli, to_cli, workspace_path, tokens_injected,
                                    core_memories_count, archive_turns_count, switched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (from_cli, to_cli, workspace_path, tokens_injected, core_count, archive_turns,
         datetime.now().isoformat()),
    )
    conn.commit()


def get_switch_history(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """Get recent switch events."""
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT * FROM switch_history ORDER BY switched_at DESC, rowid DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []


# ---------------------------------------------------------------------------
# Main switch execution
# ---------------------------------------------------------------------------

def execute_switch(
    conn: sqlite3.Connection,
    to_cli: str,
    workspace_path: str,
    from_cli: str | None = None,
    from_session_id: str | None = None,
    token_budget: int | None = None,
    include_archive_turns: int | None = None,
    conversation_ids: list[str] | None = None,
    custom_context: str | None = None,
    write_file: bool = True,
) -> dict:
    """Execute a full CLI switch.

    1. Read working memory for the workspace
    2. Read core memories (global + workspace-scoped)
    3. Read recent archive sessions
    4. Assemble context with token budgeting
    5. Write to target CLI's context file
    6. Record switch event
    7. Update working memory with new CLI info

    Returns the switch response dict.
    """
    # 1. Working memory
    working = get_working_memory(conn, workspace_path)
    if not working:
        # Create minimal working memory
        upsert_working_memory(conn, {
            "workspace_path": workspace_path,
            "last_cli": from_cli or "unknown",
            "last_session_id": from_session_id,
        })
        working = get_working_memory(conn, workspace_path)

    # Update from_cli info
    if from_cli and working:
        working["last_cli"] = from_cli
    if from_session_id and working:
        working["last_session_id"] = from_session_id

    # 2. Core memories (workspace-scoped + global)
    workspace_core = get_core_memories(conn, workspace_scope=workspace_path)
    global_core = get_core_memories(conn, workspace_scope=None)

    # Deduplicate (prefer workspace-scoped over global)
    seen_ids = set()
    merged_core = []
    for mem in workspace_core + global_core:
        mem_id = mem.get("id")
        if mem_id and mem_id not in seen_ids:
            merged_core.append(mem)
            seen_ids.add(mem_id)

    # 3. Archive sessions (use selected conversations if provided)
    if conversation_ids:
        archive_sessions = _get_sessions_by_ids(conn, conversation_ids)
    else:
        archive_sessions = get_recent_archive_sessions(conn, workspace_path=workspace_path, limit=5)

    # 4. Assemble context
    switch_count = working.get("switch_count", 0) if working else 0
    result = assemble_switch_context(
        target_cli=to_cli,
        working_memory=working,
        core_memories=merged_core,
        archive_sessions=archive_sessions,
        token_budget=token_budget,
        include_archive_turns=include_archive_turns,
        from_cli=from_cli or (working.get("last_cli") if working else None),
        switch_count=switch_count,
    )

    # 4b. Inject custom context if provided
    if custom_context and custom_context.strip():
        custom_section = f"\n## Custom Notes\n\n{custom_context.strip()}\n"
        result["content"] = result["content"].replace(
            "\n---\n_Context assembled by Memory Hub V2_\n",
            custom_section + "\n---\n_Context assembled by Memory Hub V2_\n",
        )

    # 5. Write to target file
    target_path = None
    write_skipped_reason = None
    if write_file:
        workspace = Path(workspace_path).expanduser()
        if workspace.is_absolute() and workspace.exists():
            target_rel = result["target_file"]
            target_path = workspace / Path(target_rel)
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Backup existing file
            if target_path.exists():
                backup_path = target_path.with_suffix(target_path.suffix + ".pre-switch.bak")
                backup_path.write_text(target_path.read_text(encoding="utf-8"), encoding="utf-8")

            target_path.write_text(result["content"], encoding="utf-8")
        else:
            if not workspace.is_absolute():
                write_skipped_reason = f"workspace_path is not absolute: {workspace_path}"
            else:
                write_skipped_reason = f"workspace_path does not exist: {workspace_path}"

    # 6. Record switch and increment counter
    total_tokens = result["context_assembled"]["total_tokens"]
    record_switch(
        conn, from_cli, to_cli, workspace_path,
        total_tokens, result["core_memories_injected"], result["archive_turns_injected"],
    )
    new_switch_count = increment_switch_count(conn, workspace_path)

    # 7. Update working memory
    upsert_working_memory(conn, {
        "workspace_path": workspace_path,
        "last_cli": to_cli,
    })

    # 8. Update core memory access times
    core_ids = [m.get("id") for m in merged_core[:result["core_memories_injected"]] if m.get("id")]
    update_core_memory_access(conn, core_ids)

    result["switch_number"] = new_switch_count
    result["target_file"] = str(target_path) if target_path else result["target_file"]
    if write_skipped_reason:
        result["status"] = "warning"
        result["warning"] = f"File write skipped: {write_skipped_reason}"
    else:
        result["status"] = "ok"
    result["content_preview"] = result["content"][:500] + "..." if len(result["content"]) > 500 else result["content"]

    return result


def preview_switch(
    conn: sqlite3.Connection,
    to_cli: str,
    workspace_path: str,
    token_budget: int | None = None,
    include_archive_turns: int | None = None,
    conversation_ids: list[str] | None = None,
    custom_context: str | None = None,
) -> dict:
    """Preview what would be injected without writing files or recording the switch."""
    working = get_working_memory(conn, workspace_path)

    workspace_core = get_core_memories(conn, workspace_scope=workspace_path)
    global_core = get_core_memories(conn, workspace_scope=None)
    seen_ids = set()
    merged_core = []
    for mem in workspace_core + global_core:
        mem_id = mem.get("id")
        if mem_id and mem_id not in seen_ids:
            merged_core.append(mem)
            seen_ids.add(mem_id)

    if conversation_ids:
        archive_sessions = _get_sessions_by_ids(conn, conversation_ids)
    else:
        archive_sessions = get_recent_archive_sessions(conn, workspace_path=workspace_path, limit=5)
    switch_count = working.get("switch_count", 0) if working else 0

    result = assemble_switch_context(
        target_cli=to_cli,
        working_memory=working,
        core_memories=merged_core,
        archive_sessions=archive_sessions,
        token_budget=token_budget,
        include_archive_turns=include_archive_turns,
        from_cli=working.get("last_cli") if working else None,
        switch_count=switch_count,
    )
    # Inject custom context if provided
    if custom_context and custom_context.strip():
        custom_section = f"\n## Custom Notes\n\n{custom_context.strip()}\n"
        result["content"] = result["content"].replace(
            "\n---\n_Context assembled by Memory Hub V2_\n",
            custom_section + "\n---\n_Context assembled by Memory Hub V2_\n",
        )

    result["status"] = "preview"
    result["content_preview"] = result["content"]
    return result
