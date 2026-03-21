# Memory Hub V2 Migration Guide

This guide covers migrating from Memory Hub V1 to V2, including database schema changes, API migration, and configuration updates.

---

## Overview of Changes

### What's New in V2

1. **Three-Layer Memory Architecture**: Archive (full conversations), Core (structured knowledge), Working (active task state)
2. **Structured Message Storage**: Messages stored individually with role, content_type, compression — replacing the flat `full_content` text blob
3. **CLI Quick Switch**: One-command context transfer between Claude Code, Codex CLI, Gemini CLI, and Antigravity
4. **Content Compression**: Rule-based compression for tool calls, code blocks, error stacks, thinking blocks
5. **Sync Engine**: Automatic polling + optional file watching for conversation capture
6. **Token-Budgeted Context Assembly**: Per-CLI token budgets for optimal context injection

### What's Preserved

- All V1 API endpoints remain functional (`/api/conversations`, `/api/context`, `/api/search`, etc.)
- Existing conversation data is fully preserved
- Browser extension continues to work
- Claude Code hooks remain compatible
- ChromaDB vector search unchanged

---

## Database Migration

### New Tables

| Table | Layer | Purpose |
|-------|-------|---------|
| `archive_conversations` | Archive | Full conversation metadata (replaces `conversations`) |
| `archive_messages` | Archive | Individual messages with compression |
| `working_memory` | Working | Active task state per workspace |
| `schema_version` | Meta | Tracks schema version |

### Schema Changes to Existing Tables

The `preferences` table gains new columns (added via ALTER TABLE, non-breaking):

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `pinned` | INTEGER | 0 | User-pinned memories that never decay |
| `tags` | TEXT | '[]' | JSON array of tags |
| `workspace_scope` | TEXT | NULL | NULL = global, else workspace path |
| `accessed_at` | TEXT | NULL | Last injection/view time for decay |
| `source_conversation_ids` | TEXT | '[]' | Links to archive conversations |

### Running the Migration

#### Automatic (via API)

```bash
# Start the Memory Hub server
cd backend && uvicorn main:app --port 8765

# Trigger V1 to V2 migration
curl -X POST http://localhost:8765/api/v2/migrate/v1-to-v2
```

Response:
```json
{
  "status": "ok",
  "migrated": 150,
  "skipped": 0,
  "errors": 0
}
```

#### What the Migration Does

1. Creates `archive_conversations`, `archive_messages`, `working_memory`, and `schema_version` tables
2. Copies each row from `conversations` to `archive_conversations`
3. Parses each conversation's `full_content` (the `"role: content"` flat text format) into individual `archive_messages` rows
4. Applies rule-based compression to assistant messages, storing compressed variants
5. Computes token estimates per message and per conversation
6. Preserves the original `conversations` table (renamed to `conversations_v1_backup` for safety)

#### Migration Safety

- The migration runs in a transaction — if any step fails, all changes are rolled back
- The original `conversations` table is kept as a backup
- `content_hash` dedup prevents re-migrating already-migrated conversations
- You can run the migration endpoint multiple times safely (idempotent)

---

## API Migration

### V2 Endpoints

All new endpoints are under `/api/v2/`. V1 endpoints are unchanged.

#### Conversation Ingest (V1 vs V2)

**V1** (still works):
```bash
curl -X POST http://localhost:8765/api/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "claude_code",
    "timestamp": "2026-03-18T10:00:00Z",
    "messages": [
      {"role": "user", "content": "Fix the auth bug"},
      {"role": "assistant", "content": "I will investigate..."}
    ]
  }'
```

**V2** (recommended for new integrations):
```bash
curl -X POST http://localhost:8765/api/v2/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "claude_code",
    "session_id": "session-abc-123",
    "workspace_path": "/path/to/project",
    "started_at": "2026-03-18T10:00:00Z",
    "ended_at": "2026-03-18T10:30:00Z",
    "provider": "anthropic",
    "model": "claude-opus-4-6",
    "messages": [
      {"role": "user", "content": "Fix the auth bug", "content_type": "text"},
      {"role": "assistant", "content": "I will investigate...", "content_type": "text"},
      {"role": "assistant", "content": "<tool_use>Read file: src/auth.py</tool_use>", "content_type": "tool_use", "metadata": {"tool": "Read"}}
    ],
    "working_state": {
      "active_task": "Fix auth token refresh bug",
      "plan": ["Investigate", "Fix", "Test"],
      "progress": ["Investigated - found race condition"],
      "open_issues": ["Need retry logic"]
    }
  }'
```

Key differences:
- V2 accepts `content_type` per message (text, tool_use, tool_result, image, thinking)
- V2 accepts `working_state` to auto-update working memory
- V2 stores messages individually (not as a flat text blob)
- V2 applies compression automatically

#### CLI Switch (V2 only)

```bash
# Execute a switch
curl -X POST http://localhost:8765/api/v2/switch \
  -H "Content-Type: application/json" \
  -d '{
    "to_cli": "codex",
    "workspace_path": "/path/to/project",
    "from_cli": "claude_code"
  }'

# Preview what would be injected (dry run)
curl "http://localhost:8765/api/v2/switch/preview?to_cli=codex&workspace_path=/path/to/project"
```

#### Working Memory (V2 only)

```bash
# Get working memory
curl "http://localhost:8765/api/v2/working-memory/$(urlencode /path/to/project)"

# Update working memory
curl -X PUT "http://localhost:8765/api/v2/working-memory/$(urlencode /path/to/project)" \
  -H "Content-Type: application/json" \
  -d '{
    "active_task": "Implementing auth flow",
    "current_plan": ["Fix token refresh", "Add tests", "Deploy"],
    "progress": ["Token refresh fixed"],
    "open_issues": ["Need integration tests"]
  }'

# Clear working memory
curl -X DELETE "http://localhost:8765/api/v2/working-memory/$(urlencode /path/to/project)"
```

---

## Hook Migration

### Claude Code (Enhanced)

The existing `session-start.sh` hook continues to work. V2 adds a `session-end.sh` hook:

```bash
# claude-code-integration/hooks/session-end.sh
# Captures working state when a Claude Code session ends
curl -s -X POST "http://localhost:8765/api/v2/working-memory/$(pwd)" \
  -H "Content-Type: application/json" \
  -d '{"last_cli": "claude_code", "last_session_id": "'"$SESSION_ID"'"}'
```

### Codex CLI (New)

```bash
# Before Codex session: inject context
memory-hub switch --to codex --workspace "$(pwd)" --quiet

# After Codex session: import
memory-hub import --source codex --limit 1
```

### Gemini CLI (New)

```bash
# Before Gemini CLI session: inject context
memory-hub switch --to gemini_cli --workspace "$(pwd)" --quiet
```

---

## Configuration Updates

### Sync Configuration

The sync engine runs automatically when the server starts. Configure via environment or settings:

- **Polling interval**: Default 300 seconds (5 minutes)
- **File watcher**: Optional, requires `watchdog` package
- **Limit per source**: Default 30 sessions per sync cycle

### Token Budgets

Default token budgets can be overridden per switch request via the `token_budget` parameter. Defaults:

| CLI | Total Budget |
|-----|-------------|
| Claude Code | 28,000 tokens |
| Codex CLI | 16,000 tokens |
| Gemini CLI | 111,000 tokens |
| Antigravity | 16,000 tokens |

---

## Troubleshooting

### Migration fails with "table already exists"

This is safe — the migration uses `CREATE TABLE IF NOT EXISTS` and skips already-migrated conversations. Run the migration endpoint again.

### V1 data appears missing after migration

V1 data is not deleted. Check:
- `archive_conversations` table for migrated data
- `conversations` table (or `conversations_v1_backup`) for original data
- `GET /api/v2/conversations` to browse migrated conversations

### Switch writes empty context file

Ensure working memory exists for the workspace:
```bash
curl -X PUT "http://localhost:8765/api/v2/working-memory/$(urlencode /path/to/project)" \
  -H "Content-Type: application/json" \
  -d '{"active_task": "Your current task description"}'
```

### Compression not working

Compression is applied automatically to assistant messages during ingest. Check:
- `GET /api/v2/conversations/{id}/compressed` to see compressed view
- `archive_messages.compressed` column for stored compressed variants

---

## Rollback

If you need to revert to V1:

1. V1 endpoints still work — no changes needed for existing integrations
2. The original `conversations` table (or `conversations_v1_backup`) contains all V1 data
3. V2 tables can be safely dropped without affecting V1 functionality:
   ```sql
   DROP TABLE IF EXISTS archive_messages;
   DROP TABLE IF EXISTS archive_conversations;
   DROP TABLE IF EXISTS working_memory;
   DROP TABLE IF EXISTS schema_version;
   DROP TABLE IF EXISTS switch_history;
   ```

---

**Document Version**: 1.0
**Last Updated**: 2026-03-18
