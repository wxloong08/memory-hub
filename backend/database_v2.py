"""
Memory Hub V2 -- Database layer for three-layer memory architecture.

Provides:
- archive_conversations + archive_messages tables (Archive Layer)
- working_memory table (Working Layer)
- Schema migration from V1 to V2
- Message-level CRUD operations
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

from message_compressor import compress_message, estimate_tokens


class DatabaseV2:
    """V2 database operations for the three-layer memory architecture."""

    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_v2_schema()

    def close(self):
        """Close the database connection."""
        with self._lock:
            self.conn.close()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_v2_schema(self):
        """Create V2 tables if they don't exist."""
        self.conn.executescript("""
            -- Archive Layer: full conversations
            CREATE TABLE IF NOT EXISTS archive_conversations (
                id              TEXT PRIMARY KEY,
                platform        TEXT NOT NULL,
                session_id      TEXT,
                workspace_path  TEXT,
                started_at      TEXT NOT NULL,
                ended_at        TEXT,
                message_count   INTEGER DEFAULT 0,
                token_estimate  INTEGER DEFAULT 0,
                summary         TEXT,
                summary_source  TEXT DEFAULT 'fallback',
                importance      INTEGER DEFAULT 5,
                provider        TEXT,
                model           TEXT,
                assistant_label TEXT,
                source_path     TEXT,
                source_fingerprint TEXT,
                content_hash    TEXT UNIQUE,
                metadata        TEXT DEFAULT '{}',
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_archive_platform_time
                ON archive_conversations(platform, started_at);
            CREATE INDEX IF NOT EXISTS idx_archive_workspace
                ON archive_conversations(workspace_path);
            CREATE INDEX IF NOT EXISTS idx_archive_hash
                ON archive_conversations(content_hash);
            CREATE INDEX IF NOT EXISTS idx_archive_session
                ON archive_conversations(session_id);

            -- Archive Layer: individual messages
            CREATE TABLE IF NOT EXISTS archive_messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                ordinal         INTEGER NOT NULL,
                role            TEXT NOT NULL,
                content         TEXT NOT NULL,
                content_type    TEXT DEFAULT 'text',
                compressed      TEXT,
                token_estimate  INTEGER DEFAULT 0,
                metadata        TEXT DEFAULT '{}',
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (conversation_id)
                    REFERENCES archive_conversations(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON archive_messages(conversation_id, ordinal);
            CREATE INDEX IF NOT EXISTS idx_messages_role
                ON archive_messages(conversation_id, role);

            -- Working Layer: active task context per workspace
            CREATE TABLE IF NOT EXISTS working_memory (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_path  TEXT NOT NULL UNIQUE,
                active_task     TEXT,
                current_plan    TEXT,
                progress        TEXT,
                open_issues     TEXT,
                recent_changes  TEXT,
                last_cli        TEXT,
                last_session_id TEXT,
                context_snippet TEXT,
                switch_count    INTEGER DEFAULT 0,
                updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_working_workspace
                ON working_memory(workspace_path);

            -- Schema version tracker
            CREATE TABLE IF NOT EXISTS schema_version (
                version     INTEGER PRIMARY KEY,
                applied_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            );
        """)

        # Record schema version if not present
        cursor = self.conn.execute(
            "SELECT 1 FROM schema_version WHERE version = 2"
        )
        if not cursor.fetchone():
            self.conn.execute(
                "INSERT OR IGNORE INTO schema_version (version, description) VALUES (2, 'V2 three-layer memory architecture')"
            )

        self.conn.commit()

    # ------------------------------------------------------------------
    # Archive Layer: Conversations
    # ------------------------------------------------------------------

    def add_conversation(
        self,
        platform: str,
        started_at: str,
        messages: list[dict],
        *,
        session_id: str | None = None,
        workspace_path: str | None = None,
        ended_at: str | None = None,
        summary: str | None = None,
        summary_source: str = "fallback",
        importance: int = 5,
        provider: str | None = None,
        model: str | None = None,
        assistant_label: str | None = None,
        source_path: str | None = None,
        source_fingerprint: str | None = None,
        content_hash: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, int, int]:
        """
        Insert a conversation with its messages into the archive.

        Returns (conversation_id, message_count, total_token_estimate).
        """
        with self._lock:
            # Compute content hash for dedup
            if not content_hash:
                hash_source = "\n\n".join(
                    f"{m.get('role', '')}: {m.get('content', '')}" for m in messages
                )
                content_hash = sha256(hash_source.encode("utf-8")).hexdigest()

            # Check for duplicates
            existing = self.find_existing_conversation(
                platform=platform,
                content_hash=content_hash,
                source_path=source_path,
                source_fingerprint=source_fingerprint,
            )
            if existing:
                row = self.conn.execute(
                    "SELECT message_count, token_estimate FROM archive_conversations WHERE id = ?",
                    (existing,),
                ).fetchone()
                return existing, row["message_count"] if row else 0, row["token_estimate"] if row else 0

            conv_id = str(uuid.uuid4())
            total_tokens = 0
            msg_count = 0

            # Prepare message rows (computed before insert for token totals)
            message_rows = []
            for ordinal, msg in enumerate(messages):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                content_type = msg.get("content_type", "text")
                msg_metadata = msg.get("metadata", {})

                compressed = None
                if role == "assistant" and content:
                    compressed_text = compress_message(content)
                    if compressed_text != content:
                        compressed = compressed_text

                tokens = estimate_tokens(content)
                total_tokens += tokens
                msg_count += 1
                message_rows.append((
                    conv_id, ordinal, role, content, content_type,
                    compressed, tokens, json.dumps(msg_metadata, ensure_ascii=False),
                ))

            # Insert conversation record FIRST (parent row for FK)
            self.conn.execute(
                """
                INSERT INTO archive_conversations
                    (id, platform, session_id, workspace_path, started_at, ended_at,
                     message_count, token_estimate, summary, summary_source, importance,
                     provider, model, assistant_label, source_path, source_fingerprint,
                     content_hash, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conv_id, platform, session_id, workspace_path, started_at, ended_at,
                    msg_count, total_tokens, summary, summary_source, importance,
                    provider, model, assistant_label, source_path, source_fingerprint,
                    content_hash, json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )

            # Insert messages (child rows, after parent)
            for row in message_rows:
                self.conn.execute(
                    """
                    INSERT INTO archive_messages
                        (conversation_id, ordinal, role, content, content_type,
                         compressed, token_estimate, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )

            self.conn.commit()
            return conv_id, msg_count, total_tokens

    def find_existing_conversation(
        self,
        platform: str,
        content_hash: str | None = None,
        source_path: str | None = None,
        source_fingerprint: str | None = None,
    ) -> str | None:
        """Find an existing conversation by source fingerprint or content hash."""
        with self._lock:
            if source_path and source_fingerprint:
                cursor = self.conn.execute(
                    """
                    SELECT id FROM archive_conversations
                    WHERE platform = ? AND source_path = ? AND source_fingerprint = ?
                    LIMIT 1
                    """,
                    (platform, source_path, source_fingerprint),
                )
                row = cursor.fetchone()
                if row:
                    return row["id"]

            if content_hash:
                cursor = self.conn.execute(
                    "SELECT id FROM archive_conversations WHERE platform = ? AND content_hash = ? LIMIT 1",
                    (platform, content_hash),
                )
                row = cursor.fetchone()
                if row:
                    return row["id"]

            return None

    def get_conversation(self, conversation_id: str) -> dict | None:
        """Get a conversation record by ID."""
        with self._lock:
            cursor = self.conn.execute(
                "SELECT * FROM archive_conversations WHERE id = ?",
                (conversation_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_conversations(
        self,
        *,
        workspace_path: str | None = None,
        platform: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort: str = "newest",
    ) -> tuple[list[dict], int]:
        """List conversations with filtering and pagination."""
        with self._lock:
            where_clauses: list[str] = []
            params: list[Any] = []

            if workspace_path:
                where_clauses.append("workspace_path = ?")
                params.append(workspace_path)
            if platform:
                where_clauses.append("platform = ?")
                params.append(platform)

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            order_sql = "started_at DESC" if sort == "newest" else "started_at ASC"

            count = self.conn.execute(
                f"SELECT COUNT(*) FROM archive_conversations WHERE {where_sql}",
                params,
            ).fetchone()[0]

            cursor = self.conn.execute(
                f"""
                SELECT * FROM archive_conversations
                WHERE {where_sql}
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            )
            return [dict(row) for row in cursor.fetchall()], int(count)

    def get_recent_conversations(
        self,
        workspace_path: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Get recent conversations, optionally filtered by workspace."""
        with self._lock:
            if workspace_path:
                cursor = self.conn.execute(
                    """
                    SELECT * FROM archive_conversations
                    WHERE workspace_path = ?
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    (workspace_path, limit),
                )
            else:
                cursor = self.conn.execute(
                    "SELECT * FROM archive_conversations ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and its messages (CASCADE)."""
        with self._lock:
            cursor = self.conn.execute(
                "DELETE FROM archive_conversations WHERE id = ?",
                (conversation_id,),
            )
            self.conn.commit()
            return cursor.rowcount > 0

    def update_conversation_summary(
        self,
        conversation_id: str,
        summary: str,
        summary_source: str = "ai",
    ) -> bool:
        """Update the summary of a conversation."""
        with self._lock:
            cursor = self.conn.execute(
                """
                UPDATE archive_conversations
                SET summary = ?, summary_source = ?, updated_at = ?
                WHERE id = ?
                """,
                (summary, summary_source, datetime.now().isoformat(), conversation_id),
            )
            self.conn.commit()
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Archive Layer: Messages
    # ------------------------------------------------------------------

    def get_messages(
        self,
        conversation_id: str,
        *,
        roles: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        """Get messages for a conversation, optionally filtered by role."""
        with self._lock:
            return self._get_messages_unlocked(conversation_id, roles=roles, limit=limit, offset=offset)

    def _get_messages_unlocked(
        self,
        conversation_id: str,
        *,
        roles: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        where = "conversation_id = ?"
        params: list[Any] = [conversation_id]

        if roles:
            placeholders = ",".join("?" for _ in roles)
            where += f" AND role IN ({placeholders})"
            params.extend(roles)

        query = f"SELECT * FROM archive_messages WHERE {where} ORDER BY ordinal"
        if limit:
            query += " LIMIT ? OFFSET ?"
            params.extend([int(limit), int(offset)])

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def count_messages(
        self,
        conversation_id: str,
        *,
        roles: list[str] | None = None,
    ) -> int:
        """Return the total number of messages for a conversation (with optional role filter)."""
        with self._lock:
            where = "conversation_id = ?"
            params: list[Any] = [conversation_id]

            if roles:
                placeholders = ",".join("?" for _ in roles)
                where += f" AND role IN ({placeholders})"
                params.extend(roles)

            cursor = self.conn.execute(
                f"SELECT COUNT(*) FROM archive_messages WHERE {where}", params
            )
            return cursor.fetchone()[0]

    def get_compressed_messages(self, conversation_id: str) -> list[dict]:
        """Get messages with compressed content preferred over original."""
        with self._lock:
            cursor = self.conn.execute(
                """
                SELECT id, conversation_id, ordinal, role,
                       COALESCE(compressed, content) AS content,
                       content_type, token_estimate, metadata
                FROM archive_messages
                WHERE conversation_id = ?
                ORDER BY ordinal
                """,
                (conversation_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def reconstruct_full_content(self, conversation_id: str) -> str:
        """Reconstruct the V1-style full_content string from archive_messages."""
        with self._lock:
            messages = self._get_messages_unlocked(conversation_id)
            return "\n\n".join(
                f"{msg['role']}: {msg['content']}" for msg in messages
            )

    # ------------------------------------------------------------------
    # Working Layer
    # ------------------------------------------------------------------

    def get_working_memory(self, workspace_path: str) -> dict | None:
        """Get working memory for a workspace."""
        with self._lock:
            cursor = self.conn.execute(
                "SELECT * FROM working_memory WHERE workspace_path = ?",
                (workspace_path,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            record = dict(row)
            # Parse JSON fields
            for field in ("current_plan", "progress", "open_issues"):
                if record.get(field):
                    try:
                        record[field] = json.loads(record[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            return record

    def upsert_working_memory(
        self,
        workspace_path: str,
        *,
        active_task: str | None = None,
        current_plan: list[str] | None = None,
        progress: list[str] | None = None,
        open_issues: list[str] | None = None,
        recent_changes: str | None = None,
        last_cli: str | None = None,
        last_session_id: str | None = None,
        context_snippet: str | None = None,
    ) -> dict:
        """Create or update working memory for a workspace."""
        with self._lock:
            existing = self.get_working_memory(workspace_path)
            now = datetime.now().isoformat()

            plan_json = json.dumps(current_plan, ensure_ascii=False) if current_plan is not None else None
            progress_json = json.dumps(progress, ensure_ascii=False) if progress is not None else None
            issues_json = json.dumps(open_issues, ensure_ascii=False) if open_issues is not None else None

            if existing:
                # Merge: only update fields that are provided (not None)
                updates: list[str] = ["updated_at = ?"]
                params: list[Any] = [now]

                if active_task is not None:
                    updates.append("active_task = ?")
                    params.append(active_task)
                if current_plan is not None:
                    updates.append("current_plan = ?")
                    params.append(plan_json)
                if progress is not None:
                    updates.append("progress = ?")
                    params.append(progress_json)
                if open_issues is not None:
                    updates.append("open_issues = ?")
                    params.append(issues_json)
                if recent_changes is not None:
                    updates.append("recent_changes = ?")
                    params.append(recent_changes)
                if last_cli is not None:
                    updates.append("last_cli = ?")
                    params.append(last_cli)
                if last_session_id is not None:
                    updates.append("last_session_id = ?")
                    params.append(last_session_id)
                if context_snippet is not None:
                    updates.append("context_snippet = ?")
                    params.append(context_snippet)

                params.append(workspace_path)
                self.conn.execute(
                    f"UPDATE working_memory SET {', '.join(updates)} WHERE workspace_path = ?",
                    params,
                )
            else:
                self.conn.execute(
                    """
                    INSERT INTO working_memory
                        (workspace_path, active_task, current_plan, progress, open_issues,
                         recent_changes, last_cli, last_session_id, context_snippet, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workspace_path, active_task, plan_json, progress_json, issues_json,
                        recent_changes, last_cli, last_session_id, context_snippet, now,
                    ),
                )

            self.conn.commit()
            return self.get_working_memory(workspace_path) or {}

    def increment_switch_count(self, workspace_path: str) -> int:
        """Increment the switch counter for a workspace and return new count."""
        with self._lock:
            self.conn.execute(
                """
                UPDATE working_memory
                SET switch_count = switch_count + 1, updated_at = ?
                WHERE workspace_path = ?
                """,
                (datetime.now().isoformat(), workspace_path),
            )
            self.conn.commit()
            row = self.conn.execute(
                "SELECT switch_count FROM working_memory WHERE workspace_path = ?",
                (workspace_path,),
            ).fetchone()
            return row["switch_count"] if row else 0

    def delete_working_memory(self, workspace_path: str) -> bool:
        """Clear working memory for a workspace."""
        with self._lock:
            cursor = self.conn.execute(
                "DELETE FROM working_memory WHERE workspace_path = ?",
                (workspace_path,),
            )
            self.conn.commit()
            return cursor.rowcount > 0

    def list_working_memories(self) -> list[dict]:
        """List all active working memories."""
        with self._lock:
            cursor = self.conn.execute(
                "SELECT * FROM working_memory ORDER BY updated_at DESC"
            )
            records = []
            for row in cursor.fetchall():
                record = dict(row)
                for field in ("current_plan", "progress", "open_issues"):
                    if record.get(field):
                        try:
                            record[field] = json.loads(record[field])
                        except (json.JSONDecodeError, TypeError):
                            pass
                records.append(record)
            return records

    # ------------------------------------------------------------------
    # Migration: V1 -> V2
    # ------------------------------------------------------------------

    def migrate_from_v1(self, v1_conn: sqlite3.Connection) -> dict:
        """
        Migrate data from V1 conversations table to V2 archive tables.

        Returns a summary dict with migration statistics.
        """
        with self._lock:
            cursor = v1_conn.execute(
                """
                SELECT id, platform, timestamp, project, working_dir, provider, model,
                       assistant_label, source_path, source_fingerprint, content_hash,
                       recovery_mode, summary_source, summary, full_content, importance
                FROM conversations
                """
            )

            migrated = 0
            skipped = 0
            errors = 0

            for row in cursor.fetchall():
                row_dict = dict(row) if hasattr(row, "keys") else {
                    "id": row[0], "platform": row[1], "timestamp": row[2],
                    "project": row[3], "working_dir": row[4], "provider": row[5],
                    "model": row[6], "assistant_label": row[7], "source_path": row[8],
                    "source_fingerprint": row[9], "content_hash": row[10],
                    "recovery_mode": row[11], "summary_source": row[12],
                    "summary": row[13], "full_content": row[14], "importance": row[15],
                }

                conv_id = row_dict["id"]

                # Skip if already migrated
                existing = self.conn.execute(
                    "SELECT 1 FROM archive_conversations WHERE id = ?", (conv_id,)
                ).fetchone()
                if existing:
                    skipped += 1
                    continue

                try:
                    # Parse full_content into messages
                    messages = self._parse_v1_full_content(row_dict.get("full_content") or "")

                    # Compute token estimate
                    total_tokens = sum(estimate_tokens(m.get("content", "")) for m in messages)

                    # Insert conversation
                    metadata = {}
                    if row_dict.get("recovery_mode"):
                        metadata["recovery_mode"] = row_dict["recovery_mode"]
                    if row_dict.get("project"):
                        metadata["project"] = row_dict["project"]

                    self.conn.execute(
                        """
                        INSERT INTO archive_conversations
                            (id, platform, workspace_path, started_at, message_count,
                             token_estimate, summary, summary_source, importance,
                             provider, model, assistant_label, source_path,
                             source_fingerprint, content_hash, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            conv_id, row_dict.get("platform") or "unknown",
                            row_dict.get("working_dir"), row_dict.get("timestamp") or datetime.now().isoformat(),
                            len(messages), total_tokens,
                            row_dict.get("summary"), row_dict.get("summary_source") or "fallback",
                            row_dict.get("importance") or 5,
                            row_dict.get("provider"), row_dict.get("model"),
                            row_dict.get("assistant_label"), row_dict.get("source_path"),
                            row_dict.get("source_fingerprint"), row_dict.get("content_hash"),
                            json.dumps(metadata, ensure_ascii=False),
                        ),
                    )

                    # Insert messages
                    for ordinal, msg in enumerate(messages):
                        role = msg.get("role", "user")
                        content = msg.get("content", "")
                        compressed = None
                        if role == "assistant" and content:
                            compressed_text = compress_message(content)
                            if compressed_text != content:
                                compressed = compressed_text

                        self.conn.execute(
                            """
                            INSERT INTO archive_messages
                                (conversation_id, ordinal, role, content, content_type,
                                 compressed, token_estimate, metadata)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                conv_id, ordinal, role, content, "text",
                                compressed, estimate_tokens(content), "{}",
                            ),
                        )

                    migrated += 1
                except Exception as e:
                    logger.warning(f"Migration failed for conversation {conv_id}: {e}")
                    errors += 1

            self.conn.commit()
            return {"migrated": migrated, "skipped": skipped, "errors": errors}

    @staticmethod
    def _parse_v1_full_content(full_content: str) -> list[dict]:
        """Parse V1 flat 'role: content' format into message dicts."""
        import re

        lines = full_content.replace("\r", "").split("\n")
        messages: list[dict] = []
        current: dict | None = None

        for raw_line in lines:
            match = re.match(r"^(user|assistant):\s?(.*)$", raw_line)
            if match:
                if current and str(current.get("content", "")).strip():
                    current["content"] = str(current["content"]).strip()
                    messages.append(current)
                current = {"role": match.group(1), "content": match.group(2) or ""}
                continue

            if current is None:
                continue

            current["content"] = f"{current['content']}\n{raw_line}" if current["content"] else raw_line

        if current and str(current.get("content", "")).strip():
            current["content"] = str(current["content"]).strip()
            messages.append(current)

        return messages

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get V2 database statistics."""
        with self._lock:
            conv_count = self.conn.execute(
                "SELECT COUNT(*) FROM archive_conversations"
            ).fetchone()[0]
            msg_count = self.conn.execute(
                "SELECT COUNT(*) FROM archive_messages"
            ).fetchone()[0]
            working_count = self.conn.execute(
                "SELECT COUNT(*) FROM working_memory"
            ).fetchone()[0]
            compressed_count = self.conn.execute(
                "SELECT COUNT(*) FROM archive_messages WHERE compressed IS NOT NULL"
            ).fetchone()[0]

            total_tokens = self.conn.execute(
                "SELECT COALESCE(SUM(token_estimate), 0) FROM archive_conversations"
            ).fetchone()[0]

            platforms = self.conn.execute(
                "SELECT DISTINCT platform FROM archive_conversations ORDER BY platform"
            ).fetchall()

            return {
                "archive_conversations": int(conv_count),
                "archive_messages": int(msg_count),
                "compressed_messages": int(compressed_count),
                "working_memories": int(working_count),
                "total_tokens": int(total_tokens),
                "platforms": [row[0] for row in platforms],
                "schema_version": 2,
            }
