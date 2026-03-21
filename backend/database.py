import sqlite3
from typing import List, Optional
import uuid
from datetime import datetime


LIST_SORT_SQL = {
    "newest": "timestamp DESC",
    "oldest": "timestamp ASC",
    "importance": "importance DESC, timestamp DESC",
    "ai_summary": """
        CASE summary_source
            WHEN 'ai' THEN 0
            WHEN 'imported' THEN 1
            WHEN 'fallback' THEN 2
            ELSE 3
        END ASC,
        timestamp DESC
    """,
}


class Database:
    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()
        self._ensure_schema_migrations()

    def _create_schema(self):
        """Create database schema"""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
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
                importance INTEGER DEFAULT 5,
                status TEXT DEFAULT 'completed',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                topic TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            );

            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                decision TEXT NOT NULL,
                timestamp DATETIME,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            );

            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                key TEXT,
                value TEXT,
                confidence REAL DEFAULT 0.5,
                priority INTEGER DEFAULT 0,
                client_rules TEXT DEFAULT '{}',
                status TEXT DEFAULT 'active',
                last_updated DATETIME
            );

            CREATE TABLE IF NOT EXISTS preference_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER NOT NULL,
                conversation_id TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (memory_id) REFERENCES preferences(id),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            );

            CREATE TABLE IF NOT EXISTS preference_lineage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_memory_id INTEGER NOT NULL,
                parent_memory_id INTEGER NOT NULL,
                relation_type TEXT DEFAULT 'merged',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (child_memory_id) REFERENCES preferences(id),
                FOREIGN KEY (parent_memory_id) REFERENCES preferences(id)
            );

            CREATE TABLE IF NOT EXISTS preference_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER NOT NULL,
                client_id TEXT NOT NULL,
                conversation_id TEXT,
                used_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (memory_id) REFERENCES preferences(id),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            );

            CREATE TABLE IF NOT EXISTS conversation_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_conversation_id TEXT,
                to_conversation_id TEXT,
                relation_type TEXT,
                FOREIGN KEY (from_conversation_id) REFERENCES conversations(id),
                FOREIGN KEY (to_conversation_id) REFERENCES conversations(id)
            );

            CREATE INDEX IF NOT EXISTS idx_timestamp ON conversations(timestamp);
            CREATE INDEX IF NOT EXISTS idx_platform ON conversations(platform);
            CREATE INDEX IF NOT EXISTS idx_working_dir ON conversations(working_dir);
            CREATE INDEX IF NOT EXISTS idx_preference_sources_memory_id ON preference_sources(memory_id);
            CREATE INDEX IF NOT EXISTS idx_preference_sources_conversation_id ON preference_sources(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_preference_lineage_child_memory_id ON preference_lineage(child_memory_id);
            CREATE INDEX IF NOT EXISTS idx_preference_lineage_parent_memory_id ON preference_lineage(parent_memory_id);
            CREATE INDEX IF NOT EXISTS idx_preference_usage_memory_id ON preference_usage(memory_id);
            CREATE INDEX IF NOT EXISTS idx_preference_usage_client_id ON preference_usage(client_id);
        """)
        self.conn.commit()

    def _ensure_schema_migrations(self):
        """Add newly introduced columns to existing databases."""
        cursor = self.conn.execute("PRAGMA table_info(conversations)")
        columns = {row[1] for row in cursor.fetchall()}

        migrations = {
            "provider": "ALTER TABLE conversations ADD COLUMN provider TEXT",
            "model": "ALTER TABLE conversations ADD COLUMN model TEXT",
            "assistant_label": "ALTER TABLE conversations ADD COLUMN assistant_label TEXT",
            "source_path": "ALTER TABLE conversations ADD COLUMN source_path TEXT",
            "source_fingerprint": "ALTER TABLE conversations ADD COLUMN source_fingerprint TEXT",
            "content_hash": "ALTER TABLE conversations ADD COLUMN content_hash TEXT",
            "recovery_mode": "ALTER TABLE conversations ADD COLUMN recovery_mode TEXT",
            "summary_source": "ALTER TABLE conversations ADD COLUMN summary_source TEXT",
            "memory_tier": "ALTER TABLE conversations ADD COLUMN memory_tier TEXT DEFAULT 'temporary'",
        }

        for column, statement in migrations.items():
            if column not in columns:
                self.conn.execute(statement)

        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_source_path ON conversations(source_path)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_content_hash ON conversations(content_hash)")
        preference_columns = {row[1] for row in self.conn.execute("PRAGMA table_info(preferences)").fetchall()}
        if "priority" not in preference_columns:
            self.conn.execute("ALTER TABLE preferences ADD COLUMN priority INTEGER DEFAULT 0")
        if "client_rules" not in preference_columns:
            self.conn.execute("ALTER TABLE preferences ADD COLUMN client_rules TEXT DEFAULT '{}'")
        if "status" not in preference_columns:
            self.conn.execute("ALTER TABLE preferences ADD COLUMN status TEXT DEFAULT 'active'")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS preference_lineage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_memory_id INTEGER NOT NULL,
                parent_memory_id INTEGER NOT NULL,
                relation_type TEXT DEFAULT 'merged',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (child_memory_id) REFERENCES preferences(id),
                FOREIGN KEY (parent_memory_id) REFERENCES preferences(id)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS preference_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER NOT NULL,
                client_id TEXT NOT NULL,
                conversation_id TEXT,
                used_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (memory_id) REFERENCES preferences(id),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_preference_lineage_child_memory_id ON preference_lineage(child_memory_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_preference_lineage_parent_memory_id ON preference_lineage(parent_memory_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_preference_usage_memory_id ON preference_usage(memory_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_preference_usage_client_id ON preference_usage(client_id)")

        self.conn.commit()

    def get_tables(self) -> List[str]:
        """Get list of tables in database"""
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        return [row[0] for row in cursor.fetchall()]

    def add_conversation(self, platform: str, timestamp: datetime,
                        full_content: str, project: Optional[str] = None,
                        working_dir: Optional[str] = None,
                        provider: Optional[str] = None,
                        model: Optional[str] = None,
                        assistant_label: Optional[str] = None,
                        source_path: Optional[str] = None,
                        source_fingerprint: Optional[str] = None,
                        content_hash: Optional[str] = None,
                        recovery_mode: Optional[str] = None,
                        memory_tier: Optional[str] = None,
                        summary_source: Optional[str] = None,
                        summary: Optional[str] = None,
                        importance: int = 5) -> str:
        """Add a new conversation"""
        conv_id = str(uuid.uuid4())
        self.conn.execute("""
            INSERT INTO conversations
            (id, platform, timestamp, project, working_dir, provider, model, assistant_label, source_path, source_fingerprint, content_hash, recovery_mode, memory_tier, summary_source, summary, full_content, importance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conv_id,
            platform,
            timestamp,
            project,
            working_dir,
            provider,
            model,
            assistant_label,
            source_path,
            source_fingerprint,
            content_hash,
            recovery_mode,
            memory_tier or "temporary",
            summary_source,
            summary,
            full_content,
            importance,
        ))
        self.conn.commit()
        return conv_id

    def find_existing_conversation(
        self,
        platform: str,
        timestamp: datetime,
        content_hash: Optional[str] = None,
        source_path: Optional[str] = None,
        source_fingerprint: Optional[str] = None,
    ) -> Optional[str]:
        if source_path and source_fingerprint:
            cursor = self.conn.execute(
                """
                SELECT id FROM conversations
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
                """
                SELECT id FROM conversations
                WHERE platform = ? AND timestamp = ? AND content_hash = ?
                LIMIT 1
                """,
                (platform, timestamp, content_hash),
            )
            row = cursor.fetchone()
            if row:
                return row["id"]

        return None

    def get_recent_conversations(self, hours: int = 24,
                                min_importance: int = 5,
                                working_dir: Optional[str] = None) -> List[dict]:
        """Get recent conversations"""
        query = """
            SELECT * FROM conversations
            WHERE datetime(timestamp) > datetime('now', '-' || ? || ' hours')
            AND importance >= ?
        """
        params = [hours, min_importance]

        if working_dir:
            query += " AND working_dir = ?"
            params.append(working_dir)

        query += " ORDER BY timestamp DESC"

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_recent_conversations_page(
        self,
        hours: int = 24 * 365 * 20,
        min_importance: int = 5,
        working_dir: Optional[str] = None,
        platform: Optional[str] = None,
        model_or_provider: Optional[str] = None,
        summary_source: Optional[str] = None,
        recovery_mode: Optional[str] = None,
        memory_tier: Optional[str] = None,
        query_text: Optional[str] = None,
        sort: str = "newest",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[dict], int]:
        where_clauses = [
            "datetime(timestamp) > datetime('now', '-' || ? || ' hours')",
            "importance >= ?",
        ]
        params: list = [hours, min_importance]

        if working_dir:
            where_clauses.append("working_dir = ?")
            params.append(working_dir)

        if platform:
            where_clauses.append("platform = ?")
            params.append(platform)

        if model_or_provider:
            where_clauses.append("(model = ? OR provider = ?)")
            params.extend([model_or_provider, model_or_provider])

        if summary_source:
            where_clauses.append("summary_source = ?")
            params.append(summary_source)

        if recovery_mode:
            where_clauses.append("recovery_mode = ?")
            params.append(recovery_mode)

        if memory_tier:
            where_clauses.append("memory_tier = ?")
            params.append(memory_tier)

        if query_text:
            where_clauses.append(
                """
                (
                    lower(coalesce(summary, '')) LIKE ?
                    OR lower(coalesce(project, '')) LIKE ?
                    OR lower(coalesce(model, '')) LIKE ?
                    OR lower(coalesce(provider, '')) LIKE ?
                    OR lower(coalesce(assistant_label, '')) LIKE ?
                    OR lower(coalesce(platform, '')) LIKE ?
                )
                """
            )
            like_query = f"%{query_text.strip().lower()}%"
            params.extend([like_query] * 6)

        where_sql = " AND ".join(where_clauses)
        order_sql = LIST_SORT_SQL.get(sort, LIST_SORT_SQL["newest"])

        count_cursor = self.conn.execute(
            f"SELECT COUNT(*) FROM conversations WHERE {where_sql}",
            params,
        )
        total = int(count_cursor.fetchone()[0])

        data_cursor = self.conn.execute(
            f"""
            SELECT * FROM conversations
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        )
        return [dict(row) for row in data_cursor.fetchall()], total

    def get_conversations_for_resummary(self, limit: int = 20) -> List[dict]:
        cursor = self.conn.execute(
            """
            SELECT *
            FROM conversations
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_conversation_filter_values(self) -> dict:
        fields = {
            "platforms": "platform",
            "models": "coalesce(model, provider)",
            "summary_sources": "summary_source",
            "recovery_modes": "recovery_mode",
            "memory_tiers": "memory_tier",
        }
        result = {}

        for key, expression in fields.items():
            cursor = self.conn.execute(
                f"""
                SELECT DISTINCT {expression} AS value
                FROM conversations
                WHERE trim(coalesce({expression}, '')) != ''
                ORDER BY value COLLATE NOCASE ASC
                """
            )
            result[key] = [row["value"] for row in cursor.fetchall() if row["value"]]

        return result

    def delete_conversation(self, conversation_id: str) -> bool:
        cursor = self.conn.execute("DELETE FROM topics WHERE conversation_id = ?", (conversation_id,))
        cursor = self.conn.execute("DELETE FROM decisions WHERE conversation_id = ?", (conversation_id,))
        cursor = self.conn.execute(
            "DELETE FROM conversation_relations WHERE from_conversation_id = ? OR to_conversation_id = ?",
            (conversation_id, conversation_id),
        )
        cursor = self.conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def update_memory_tier(self, conversation_id: str, memory_tier: str) -> bool:
        cursor = self.conn.execute(
            "UPDATE conversations SET memory_tier = ? WHERE id = ?",
            (memory_tier, conversation_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0
