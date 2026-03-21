# Memory Hub V2 API Reference

**Version**: 2.0
**Date**: 2026-03-18
**Base URL**: `http://localhost:8765`

---

## Table of Contents

1. [Overview](#1-overview)
2. [V2 Endpoints -- Archive Layer (Conversations)](#2-v2-endpoints----archive-layer-conversations)
3. [V2 Endpoints -- Working Memory](#3-v2-endpoints----working-memory)
4. [V2 Endpoints -- CLI Switch](#4-v2-endpoints----cli-switch)
5. [V2 Endpoints -- Import & Sync](#5-v2-endpoints----import--sync)
6. [V2 Endpoints -- Stats & Migration](#6-v2-endpoints----stats--migration)
7. [V1 Endpoints Reference (Preserved)](#7-v1-endpoints-reference-preserved)
8. [V1 to V2 Migration Guide](#8-v1-to-v2-migration-guide)
9. [CLI Tool: memory-hub](#9-cli-tool-memory-hub)
10. [Hook Configuration Guide](#10-hook-configuration-guide)
11. [Error Handling](#11-error-handling)
12. [Data Models](#12-data-models)

---

## 1. Overview

Memory Hub V2 introduces a **three-layer memory architecture**:

| Layer | Storage | Purpose | V2 API Prefix |
|-------|---------|---------|---------------|
| **Archive** | `archive_conversations` + `archive_messages` | Full conversation transcripts | `/api/v2/conversations` |
| **Core** | `preferences` (extended) | Structured knowledge (facts, decisions, preferences) | `/api/memories` (V1, still active) |
| **Working** | `working_memory` | Active task context per workspace | `/api/v2/working-memory` |

**Key principle**: All V2 endpoints live under `/api/v2/`. V1 endpoints remain fully functional and are not removed.

### Authentication

No authentication is required -- Memory Hub runs locally on `127.0.0.1:8765`.

### Content-Type

All POST/PUT requests expect `Content-Type: application/json`.

### Pagination Convention

Paginated endpoints use `limit` (max items, default 50) and `offset` (skip N items, default 0). Responses include `total` for the unfiltered count.

---

## 2. V2 Endpoints -- Archive Layer (Conversations)

### POST /api/v2/conversations

**Ingest a full conversation with structured messages.** This is the primary V2 ingest endpoint.

**Request Body:**

```json
{
    "platform": "claude_code",
    "session_id": "session-abc-123",
    "workspace_path": "D:\\pythonproject\\my-project",
    "started_at": "2026-03-18T10:00:00Z",
    "ended_at": "2026-03-18T10:45:00Z",
    "provider": "anthropic",
    "model": "claude-opus-4-6",
    "assistant_label": "Claude",
    "messages": [
        {
            "role": "user",
            "content": "Fix the auth token refresh bug",
            "content_type": "text",
            "metadata": {}
        },
        {
            "role": "assistant",
            "content": "I'll investigate the auth module...",
            "content_type": "text",
            "metadata": {}
        },
        {
            "role": "assistant",
            "content": "<tool_use>Read file: src/auth.py, 238 lines</tool_use>",
            "content_type": "tool_use",
            "metadata": {"tool": "Read", "path": "src/auth.py"}
        }
    ],
    "working_state": {
        "active_task": "Fix auth token refresh bug",
        "plan": ["Investigate root cause", "Apply fix", "Write tests"],
        "progress": ["Investigated - found race condition"],
        "open_issues": ["Need to add retry logic"],
        "recent_changes": "Modified src/auth.py"
    },
    "summary": null,
    "metadata": {},
    "source_path": null,
    "source_fingerprint": null,
    "project": "auth-system"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `platform` | string | Yes | Source platform: `claude_code`, `codex`, `gemini_cli`, `antigravity`, `claude_web`, `chatgpt`, `gemini_web`, `grok`, `deepseek` |
| `session_id` | string | No | Original session ID from the CLI/platform |
| `workspace_path` | string | No | Working directory (for code CLIs) |
| `started_at` | string | Yes | Session start time (ISO 8601) |
| `ended_at` | string | No | Session end time |
| `provider` | string | No | AI provider (`anthropic`, `openai`, `google`, `xai`, `deepseek`) |
| `model` | string | No | Model name (e.g., `claude-opus-4-6`) |
| `assistant_label` | string | No | Display name for the assistant |
| `messages` | array | Yes | Array of `MessageInput` objects (min 1) |
| `messages[].role` | string | Yes | `user`, `assistant`, `system`, or `tool` |
| `messages[].content` | string | Yes | Full message content |
| `messages[].content_type` | string | No | Default `text`. Options: `text`, `tool_use`, `tool_result`, `image`, `thinking` |
| `messages[].metadata` | object | No | Tool name, file paths, etc. |
| `working_state` | object | No | If provided with `workspace_path`, auto-updates working memory |
| `summary` | string | No | Pre-computed summary. If null, auto-derived from messages. |
| `metadata` | object | No | Extensible metadata (JSON) |
| `source_path` | string | No | Original file path (for imported sessions) |
| `source_fingerprint` | string | No | File fingerprint for dedup |
| `project` | string | No | Project name/title |

**Response (200):**

```json
{
    "status": "ok",
    "conversation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "message_count": 15,
    "token_estimate": 12500,
    "summary": "Fix auth token refresh bug: Investigated race condition...",
    "working_memory_updated": true
}
```

**Dedup**: Uses `content_hash` (SHA-256 of all messages). If a conversation with the same hash already exists, the existing ID is returned without creating a duplicate.

---

### GET /api/v2/conversations

**List conversations with filtering and pagination.**

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `workspace_path` | string | null | Filter by workspace |
| `platform` | string | null | Filter by platform |
| `limit` | int | 50 | Max results (1-200) |
| `offset` | int | 0 | Skip N results |
| `sort` | string | `newest` | Sort order: `newest`, `oldest` |

**Example:**

```bash
curl "http://localhost:8765/api/v2/conversations?platform=claude_code&limit=10"
```

**Response (200):**

```json
{
    "conversations": [
        {
            "id": "a1b2c3d4-...",
            "platform": "claude_code",
            "session_id": "session-abc-123",
            "workspace_path": "D:\\pythonproject\\my-project",
            "started_at": "2026-03-18T10:00:00Z",
            "ended_at": "2026-03-18T10:45:00Z",
            "message_count": 15,
            "token_estimate": 12500,
            "summary": "Fix auth token refresh bug...",
            "summary_source": "fallback",
            "importance": 7,
            "provider": "anthropic",
            "model": "claude-opus-4-6",
            "assistant_label": "Claude",
            "content_hash": "abc123...",
            "metadata": {},
            "created_at": "2026-03-18T10:45:00Z",
            "updated_at": "2026-03-18T10:45:00Z"
        }
    ],
    "total": 142,
    "limit": 10,
    "offset": 0
}
```

---

### GET /api/v2/conversations/{conversation_id}

**Get a conversation with all its messages.**

**Response (200):**

```json
{
    "id": "a1b2c3d4-...",
    "platform": "claude_code",
    "started_at": "2026-03-18T10:00:00Z",
    "message_count": 15,
    "summary": "Fix auth token refresh bug...",
    "messages": [
        {
            "id": 1,
            "conversation_id": "a1b2c3d4-...",
            "ordinal": 0,
            "role": "user",
            "content": "Fix the auth token refresh bug",
            "content_type": "text",
            "compressed": null,
            "token_estimate": 12,
            "metadata": {}
        },
        {
            "id": 2,
            "conversation_id": "a1b2c3d4-...",
            "ordinal": 1,
            "role": "assistant",
            "content": "I'll investigate the auth module...",
            "content_type": "text",
            "compressed": null,
            "token_estimate": 450,
            "metadata": {}
        }
    ]
}
```

**Error (404):** `{"detail": "Conversation not found"}`

---

### GET /api/v2/conversations/{conversation_id}/messages

**Get messages for a conversation with optional filtering.**

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `role` | string | null | Filter by role (`user`, `assistant`, `system`, `tool`) |
| `limit` | int | 100 | Max results (1-1000) |
| `offset` | int | 0 | Skip N results |

**Example:**

```bash
curl "http://localhost:8765/api/v2/conversations/a1b2c3d4.../messages?role=user"
```

**Response (200):**

```json
{
    "messages": [
        {
            "id": 1,
            "ordinal": 0,
            "role": "user",
            "content": "Fix the auth token refresh bug",
            "content_type": "text",
            "compressed": null,
            "token_estimate": 12,
            "metadata": {}
        }
    ],
    "total": 5
}
```

---

### GET /api/v2/conversations/{conversation_id}/compressed

**Get the compressed version of a conversation's messages.** Useful for previewing what would be injected during a CLI switch.

**Response (200):**

```json
{
    "conversation_id": "a1b2c3d4-...",
    "messages": [
        {
            "ordinal": 0,
            "role": "user",
            "content": "Fix the auth token refresh bug"
        },
        {
            "ordinal": 1,
            "role": "assistant",
            "content": "I'll investigate the auth module..."
        },
        {
            "ordinal": 2,
            "role": "assistant",
            "content": "[Read: src/auth.py, 238 lines]"
        }
    ],
    "original_tokens": 12500,
    "compressed_tokens": 3200,
    "compression_ratio": 0.256
}
```

---

### DELETE /api/v2/conversations/{conversation_id}

**Delete a conversation and all its messages.** Cascading delete removes `archive_messages` rows.

**Response (200):** `{"status": "ok", "deleted": "a1b2c3d4-..."}`

**Error (404):** `{"detail": "Conversation not found"}`

---

## 3. V2 Endpoints -- Working Memory

Working memory tracks the **active task state** per workspace directory. It enables seamless CLI switching by preserving what you were doing, where you left off, and what problems remain.

### GET /api/v2/working-memory

**List all active working memories across all workspaces.**

**Response (200):**

```json
{
    "working_memories": [
        {
            "id": 1,
            "workspace_path": "D:\\pythonproject\\my-project",
            "active_task": "Fix auth token refresh bug",
            "current_plan": ["Investigate", "Fix", "Test"],
            "progress": ["Investigated - found race condition"],
            "open_issues": ["Need retry logic"],
            "recent_changes": "Modified src/auth.py",
            "last_cli": "claude_code",
            "last_session_id": "a1b2c3d4-...",
            "context_snippet": "...",
            "switch_count": 2,
            "updated_at": "2026-03-18T10:45:00"
        }
    ]
}
```

---

### GET /api/v2/working-memory/{workspace_path}

**Get working memory for a specific workspace.**

The `workspace_path` is a URL-encoded absolute path.

**Example:**

```bash
# URL-encode the path
curl "http://localhost:8765/api/v2/working-memory/D%3A%5Cpythonproject%5Cmy-project"
```

**Response (200):**

```json
{
    "id": 1,
    "workspace_path": "D:\\pythonproject\\my-project",
    "active_task": "Fix auth token refresh bug",
    "current_plan": ["Investigate", "Fix", "Test"],
    "progress": ["Investigated - found race condition"],
    "open_issues": ["Need retry logic"],
    "recent_changes": "Modified src/auth.py",
    "last_cli": "claude_code",
    "last_session_id": "a1b2c3d4-...",
    "context_snippet": "Last 3 turns of conversation...",
    "switch_count": 2,
    "updated_at": "2026-03-18T10:45:00"
}
```

**Error (404):** `{"detail": "No working memory found"}`

---

### PUT /api/v2/working-memory/{workspace_path}

**Create or update working memory for a workspace (upsert).** Only provided fields are updated; omitted fields retain their current values.

**Request Body:**

```json
{
    "workspace_path": "D:\\pythonproject\\my-project",
    "active_task": "Fix auth token refresh bug",
    "current_plan": ["Investigate root cause", "Apply fix", "Write tests"],
    "progress": ["Step 1 done: found race condition in token_refresh()"],
    "open_issues": ["Need to add retry logic", "Review error handling"],
    "recent_changes": "Modified src/auth.py lines 42-55",
    "last_cli": "claude_code",
    "last_session_id": "a1b2c3d4-...",
    "context_snippet": "User asked to fix auth bug. Found race condition..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workspace_path` | string | Yes | Absolute path to workspace |
| `active_task` | string | No | Current task description |
| `current_plan` | array[string] | No | Ordered step list |
| `progress` | array[string] | No | Completed steps |
| `open_issues` | array[string] | No | Blockers, TODOs |
| `recent_changes` | string | No | Recent code modifications summary |
| `last_cli` | string | No | Last CLI used |
| `last_session_id` | string | No | Last conversation ID |
| `context_snippet` | string | No | Key conversation excerpt |

**Response (200):**

```json
{
    "status": "ok",
    "workspace_path": "D:\\pythonproject\\my-project",
    "action": "updated"
}
```

---

### DELETE /api/v2/working-memory/{workspace_path}

**Clear working memory for a workspace.** Use this when a task is complete.

**Response (200):** `{"status": "ok", "deleted": true}`

**Error (404):** `{"detail": "No working memory found"}`

---

## 4. V2 Endpoints -- CLI Switch

The switch system orchestrates context transfer between CLIs by assembling a three-layer context document and writing it to the target CLI's context file.

### POST /api/v2/switch

**Execute a CLI switch with context injection.** This is the core V2 operation.

**Request Body:**

```json
{
    "from_cli": "claude_code",
    "to_cli": "codex",
    "workspace_path": "D:\\pythonproject\\my-project",
    "from_session_id": "a1b2c3d4-...",
    "token_budget": null,
    "include_archive_turns": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `to_cli` | string | Yes | Target CLI: `claude_code`, `codex`, `gemini_cli`, `antigravity` |
| `workspace_path` | string | Yes | Absolute path to workspace |
| `from_cli` | string | No | Source CLI (logged for history) |
| `from_session_id` | string | No | Session to capture state from |
| `token_budget` | int | No | Override default token budget (see table below) |
| `include_archive_turns` | int | No | Override number of archive turns to include |

**Default Token Budgets:**

| Target CLI | Working | Core | Archive | Total |
|-----------|---------|------|---------|-------|
| `claude_code` | 3,000 | 5,000 | 20,000 | 28,000 |
| `codex` | 2,000 | 4,000 | 10,000 | 16,000 |
| `gemini_cli` | 3,000 | 8,000 | 100,000 | 111,000 |
| `antigravity` | 2,000 | 4,000 | 10,000 | 16,000 |

**Response (200):**

```json
{
    "status": "ok",
    "target_file": "D:\\pythonproject\\my-project\\AGENTS.md",
    "target_cli": "codex",
    "context_assembled": {
        "working_memory_tokens": 1200,
        "core_memory_tokens": 3500,
        "archive_tokens": 8000,
        "total_tokens": 12700
    },
    "core_memories_injected": 8,
    "archive_turns_injected": 12,
    "switch_number": 3,
    "content_preview": "# Resume Context: Fix auth bug\n\n## Current Task\n..."
}
```

**Target Files per CLI:**

| CLI | Context File | Path |
|-----|-------------|------|
| Claude Code | `CLAUDE.md` | `{workspace}/.claude/CLAUDE.md` |
| Codex CLI | `AGENTS.md` | `{workspace}/AGENTS.md` |
| Gemini CLI | `GEMINI.md` | `{workspace}/GEMINI.md` |
| Antigravity | `context.md` | `{workspace}/.antigravity/context.md` |

**Error (400):** `{"detail": "Unsupported CLI: ..."}`

---

### GET /api/v2/switch/preview

**Preview what would be injected (dry run).** Does not write any files.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `to_cli` | string | Yes | Target CLI |
| `workspace_path` | string | Yes | Workspace path |
| `token_budget` | int | No | Override token budget |

**Example:**

```bash
curl "http://localhost:8765/api/v2/switch/preview?to_cli=codex&workspace_path=D%3A%5Cproject"
```

**Response (200):** Same structure as `POST /api/v2/switch` but no files are written.

---

### GET /api/v2/switch/history

**List recent switch events.**

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 20 | Max entries |

**Response (200):**

```json
{
    "history": [
        {
            "id": 1,
            "from_cli": "claude_code",
            "to_cli": "codex",
            "workspace_path": "D:\\pythonproject\\my-project",
            "tokens_injected": 12700,
            "core_memories_count": 8,
            "archive_turns_count": 12,
            "switched_at": "2026-03-18T10:50:00"
        }
    ]
}
```

---

## 5. V2 Endpoints -- Import & Sync

### POST /api/v2/import/local

**Import local CLI sessions into V2 archive tables.**

**Request Body:**

```json
{
    "source": "all",
    "limit": 20,
    "dry_run": false,
    "auto_summarize": true,
    "auto_compress": true
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | string | `all` | Import source: `all`, `claude_code`, `codex`, `gemini_cli`, `antigravity` |
| `limit` | int | 20 | Max sessions per source (1-200) |
| `dry_run` | bool | false | Preview without importing |
| `auto_summarize` | bool | true | Generate AI summaries for imported sessions |
| `auto_compress` | bool | true | Apply rule-based compression |

**Response (200):**

```json
{
    "imported": 8,
    "skipped": 42,
    "sources": [
        {
            "source": "claude_code",
            "imported": 3,
            "skipped": 15,
            "conversation_ids": ["id1", "id2", "id3"]
        },
        {
            "source": "codex",
            "imported": 2,
            "skipped": 10,
            "conversation_ids": ["id4", "id5"]
        }
    ],
    "dry_run": false,
    "requested_source": "all",
    "storage": "v2_archive"
}
```

**Source Directories:**

| Source | Path |
|--------|------|
| `claude_code` | `~/.claude/projects/` |
| `codex` | `~/.codex/sessions/` |
| `gemini_cli` | `~/.gemini/tmp/` |
| `antigravity` | `~/.gemini/antigravity/conversations/` |

---

### GET /api/v2/sync/status

**Get current sync status including file watcher and polling info.**

**Response (200):**

```json
{
    "status": "running",
    "last_sync": "2026-03-18T10:30:00",
    "sources": {
        "claude_code": {"watching": true, "last_import": "2026-03-18T10:30:00"},
        "codex": {"watching": true, "last_import": "2026-03-18T09:15:00"},
        "gemini_cli": {"watching": true, "last_import": "2026-03-18T10:00:00"},
        "antigravity": {"watching": true, "last_import": "2026-03-18T08:45:00"}
    }
}
```

---

### POST /api/v2/sync/trigger

**Manually trigger an incremental sync of local CLI sessions.**

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | `all` | Source to sync |
| `limit` | int | 30 | Max sessions per source |

**Example:**

```bash
curl -X POST "http://localhost:8765/api/v2/sync/trigger?source=claude_code&limit=10"
```

---

## 6. V2 Endpoints -- Stats & Migration

### GET /api/v2/stats

**Get V2 database statistics.**

**Response (200):**

```json
{
    "archive": {
        "conversation_count": 142,
        "message_count": 3850,
        "total_tokens": 1250000,
        "by_platform": {
            "claude_code": 45,
            "codex": 30,
            "gemini_cli": 25,
            "antigravity": 20,
            "claude_web": 22
        }
    },
    "working_memory": {
        "active_workspaces": 3
    },
    "switches": {
        "total": 15
    }
}
```

---

### POST /api/v2/migrate/v1-to-v2

**Migrate V1 conversations table to V2 archive tables.** This is a one-time operation. Safe to run multiple times (skips already-migrated records).

**Request Body:** None

**Response (200):**

```json
{
    "status": "ok",
    "migrated_conversations": 85,
    "migrated_messages": 2340,
    "skipped": 0,
    "errors": []
}
```

---

## 7. V1 Endpoints Reference (Preserved)

All V1 endpoints remain functional. They operate on the original `conversations` and `preferences` tables.

### Conversations (V1)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/conversations` | Add a conversation (flat content format) |
| `GET` | `/api/conversations/list` | List conversations with pagination & filters |
| `GET` | `/api/conversations/filters` | Get filter options (platforms, models, etc.) |
| `GET` | `/api/conversations/{id}` | Get single conversation |
| `DELETE` | `/api/conversations/{id}` | Delete a conversation |
| `POST` | `/api/conversations/{id}/memory-tier` | Set memory tier (`temporary`, `saved`, `pinned`) |
| `GET` | `/api/conversations/{id}/memories` | List memories linked to a conversation |
| `GET` | `/api/conversations/{id}/export` | Generate export for a CLI |
| `POST` | `/api/conversations/{id}/export/apply` | Write export to workspace |

### Context & Search (V1)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/context` | Get context summary for CLAUDE.md injection |
| `GET` | `/api/search` | Semantic search (ChromaDB) |
| `GET` | `/api/related/{id}` | Find related conversations |

### Memories / Core Layer (V1 -- still the primary memory API)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/memories` | List all memories (with enrichment) |
| `POST` | `/api/memories` | Create a memory |
| `POST` | `/api/memories/{id}` | Update a memory |
| `DELETE` | `/api/memories/{id}` | Delete a memory |
| `POST` | `/api/memories/{id}/status` | Set status (`active`, `archived`) |
| `POST` | `/api/memories/{id}/priority` | Set priority (0-100) |
| `POST` | `/api/memories/{id}/client-rules` | Set per-CLI include/exclude rules |
| `POST` | `/api/memories/merge` | Merge two memories into one |
| `POST` | `/api/memories/extract/{conversation_id}` | Extract memories from a conversation |
| `GET` | `/api/memories/suggestions` | Get merge suggestions |
| `GET` | `/api/memories/conflicts` | Get conflict suggestions |
| `GET` | `/api/memories/cleanup-suggestions` | Get cleanup suggestions |
| `POST` | `/api/memories/conflicts/resolve` | Resolve a memory conflict |
| `POST` | `/api/memories/export-simulate` | Preview export with custom prompt |

### AI & Analysis (V1)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/ai/status` | AI provider availability |
| `POST` | `/api/ai/reload` | Reload AI configuration |
| `POST` | `/api/analyze/{id}` | Run AI analysis on a conversation |
| `POST` | `/api/conversations/resummarize` | Re-summarize specific conversations |
| `POST` | `/api/conversations/resummarize-ugly` | Re-summarize conversations with bad titles |

### Import & Export (V1)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/import/local` | Import local CLI sessions (V1 storage) |
| `GET` | `/api/export/clients` | List export targets |

### Backup (V1)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/backup/export` | Create backup bundle |
| `GET` | `/api/backup/settings` | Get backup settings |
| `POST` | `/api/backup/settings` | Update backup settings |
| `POST` | `/api/backup/restore` | Restore from backup |
| `GET` | `/api/backup/preview` | Preview backup contents |
| `GET` | `/api/backup/validate` | Validate a backup file |

### System (V1)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/stats` | System statistics |

---

## 8. V1 to V2 Migration Guide

### 8.1 What Changed

| Concept | V1 | V2 |
|---------|----|----|
| Conversation storage | `conversations.full_content` (flat text) | `archive_conversations` + `archive_messages` (structured) |
| Message access | Parse `full_content` text manually | `GET /api/v2/conversations/{id}/messages` |
| CLI switching | Manual: export then import | `POST /api/v2/switch` (one step) |
| Task state | Not tracked | `working_memory` table |
| Content compression | Not implemented | `archive_messages.compressed` (auto-generated) |
| Import storage | `conversations` table | `archive_conversations` + `archive_messages` |

### 8.2 Endpoint Migration Map

| V1 Endpoint | V2 Replacement | Notes |
|-------------|---------------|-------|
| `POST /api/conversations` | `POST /api/v2/conversations` | V2 accepts structured messages instead of flat content |
| `GET /api/conversations/list` | `GET /api/v2/conversations` | V2 uses `archive_conversations` table |
| `GET /api/conversations/{id}` | `GET /api/v2/conversations/{id}` | V2 includes `messages` array |
| `DELETE /api/conversations/{id}` | `DELETE /api/v2/conversations/{id}` | V2 cascades to messages |
| `POST /api/import/local` | `POST /api/v2/import/local` | V2 stores to archive tables with compression |
| `GET /api/export/clients` | Unchanged | Still uses V1 endpoint |
| `GET /api/context` | `GET /api/v2/switch/preview` | V2 provides richer three-layer context |
| (none) | `POST /api/v2/switch` | New in V2 |
| (none) | `/api/v2/working-memory/*` | New in V2 |
| `/api/memories/*` | Unchanged | Core memories remain on V1 API |

### 8.3 Migration Procedure

1. **Start the backend** -- V2 tables are auto-created on startup by `DatabaseV2._ensure_v2_schema()`

2. **Run the migration** -- Call the one-time migration endpoint:

```bash
curl -X POST http://localhost:8765/api/v2/migrate/v1-to-v2
```

This copies V1 `conversations` rows to `archive_conversations` and parses `full_content` into `archive_messages`.

3. **Verify** -- Check V2 stats:

```bash
curl http://localhost:8765/api/v2/stats
```

4. **Switch importers** -- Update your import workflows to use `POST /api/v2/import/local` instead of `POST /api/import/local`.

5. **V1 endpoints remain active** -- No need to change existing browser extension or Claude Code hooks immediately. They can continue using V1 endpoints.

### 8.4 Coexistence

V1 and V2 endpoints operate on **separate tables**. A conversation can exist in V1 (`conversations`) and V2 (`archive_conversations`) independently. The migration endpoint copies from V1 to V2 but does not remove V1 data.

---

## 9. CLI Tool: memory-hub

The `memory-hub` CLI wraps the V2 API for terminal usage. Located at `cli/memory_hub.py`.

### Installation

```bash
# From the project root
export PATH="$PATH:$(pwd)/cli"
# Or on Windows:
set PATH=%PATH%;%cd%\cli

# Verify
python cli/memory_hub.py --help
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORY_HUB_URL` | `http://localhost:8765` | Memory Hub API URL |

### Commands

#### memory-hub switch

Switch to another CLI with full context injection.

```bash
# Basic switch: current directory, default budget
memory-hub switch --to codex

# Switch with explicit workspace
memory-hub switch --to gemini_cli --workspace /path/to/project

# Override token budget
memory-hub switch --to codex --budget 20000

# Limit archive turns
memory-hub switch --to codex --turns 5

# Preview mode (dry run, no file writes)
memory-hub switch --to codex --preview

# Preview with full content output
memory-hub switch --to codex --preview --verbose

# Quiet mode (minimal output)
memory-hub switch --to codex --quiet
```

**Supported targets**: `claude_code`, `codex`, `gemini_cli`, `antigravity`

#### memory-hub status

Show current working memory for a workspace.

```bash
# Current directory
memory-hub status

# Specific workspace
memory-hub status --workspace /path/to/project
```

**Example output:**

```
Working Memory: D:\pythonproject\my-project
  Task: Fix auth token refresh bug
  Last CLI: claude_code
  Switches: 2
  Updated: 2026-03-18T10:45:00
  Plan:
    1. Investigate root cause
    2. Apply fix
    3. Write tests
  Completed:
    - Investigated - found race condition
  Open Issues:
    - Need retry logic
```

#### memory-hub save-state

Manually save working state (useful when hooks don't capture everything).

```bash
# Save task description
memory-hub save-state --task "Implementing JWT auth flow"

# Save task with plan
memory-hub save-state --task "Implementing JWT auth" --plan "1. Design schema, 2. Implement endpoints, 3. Write tests"

# Tag which CLI you're using
memory-hub save-state --task "Bug fix" --cli claude_code

# Specific workspace
memory-hub save-state --task "Deploy config" --workspace /path/to/project
```

#### memory-hub import

Import local CLI sessions into V2 archive.

```bash
# Import all sources (default: 20 per source)
memory-hub import --source all

# Import specific source
memory-hub import --source claude_code --limit 50

# Import Codex sessions only
memory-hub import --source codex --limit 10
```

#### memory-hub search

Search conversations across all platforms.

```bash
# Basic search
memory-hub search "auth token bug"

# Limit results
memory-hub search "database migration" --limit 10
```

**Example output:**

```
Conversations (3):
  [claude_code] Fix auth token refresh race condition
    Importance: 8/10  |  2026-03-18T10:00:00
  [codex] Auth system JWT implementation
    Importance: 7/10  |  2026-03-17T14:30:00
  [claude_web] Discussion about token refresh strategies
    Importance: 6/10  |  2026-03-16T09:00:00

Memories (1):
  [decision] auth_design: Using JWT with rotating refresh tokens
```

#### memory-hub history

Show switch history.

```bash
memory-hub history
memory-hub history --limit 5
```

**Example output:**

```
Switch History (3 entries):
  claude_code -> codex  |  12700 tokens  |  2026-03-18T10:50:00
    Workspace: D:\pythonproject\my-project
  codex -> gemini_cli  |  45000 tokens  |  2026-03-18T11:30:00
    Workspace: D:\pythonproject\my-project
  gemini_cli -> claude_code  |  22000 tokens  |  2026-03-18T14:00:00
    Workspace: D:\pythonproject\my-project
```

---

## 10. Hook Configuration Guide

Hooks automate context injection at CLI session start and state capture at session end.

### 10.1 Claude Code Hooks

Claude Code supports `PreToolUse`, `PostToolUse`, and notification hooks via `.claude/settings.json`.

**Session Start Hook** (injects context from Memory Hub):

File: `claude-code-integration/hooks/session-start.sh`

```bash
#!/bin/bash
# Inject Memory Hub context into CLAUDE.md on session start.
# Called by Claude Code's session-start hook.

MEMORY_HUB_URL="${MEMORY_HUB_URL:-http://localhost:8765}"
WORKSPACE="$(pwd)"

# Silently skip if Memory Hub is not running
if ! curl -sf "${MEMORY_HUB_URL}/health" > /dev/null 2>&1; then
    exit 0
fi

# Fetch context and write to CLAUDE.md
curl -sf "${MEMORY_HUB_URL}/api/context?working_dir=${WORKSPACE}&hours=48&min_importance=5" \
    | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    context = data.get('context', '')
    if context:
        print(context)
except:
    pass
" > /tmp/memory-hub-context.md 2>/dev/null

if [ -s /tmp/memory-hub-context.md ]; then
    mkdir -p .claude
    CLAUDE_MD=".claude/CLAUDE.md"
    if [ -f "$CLAUDE_MD" ]; then
        # Preserve content after "# Original Memory" marker
        ORIGINAL=$(sed -n '/^# Original Memory/,$p' "$CLAUDE_MD" 2>/dev/null)
        if [ -z "$ORIGINAL" ]; then
            ORIGINAL=$(cat "$CLAUDE_MD")
            echo -e "$(cat /tmp/memory-hub-context.md)\n\n---\n\n# Original Memory\n\n${ORIGINAL}" > "$CLAUDE_MD"
        else
            echo -e "$(cat /tmp/memory-hub-context.md)\n\n---\n\n${ORIGINAL}" > "$CLAUDE_MD"
        fi
    else
        cp /tmp/memory-hub-context.md "$CLAUDE_MD"
    fi
fi
rm -f /tmp/memory-hub-context.md
```

**Session End Hook** (captures working state):

File: `claude-code-integration/hooks/session-end.sh`

```bash
#!/bin/bash
# Capture working state when Claude Code session ends.

MEMORY_HUB_URL="${MEMORY_HUB_URL:-http://localhost:8765}"
WORKSPACE="$(pwd)"
ENCODED_WORKSPACE=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${WORKSPACE}', safe=''))")

curl -sf -X PUT "${MEMORY_HUB_URL}/api/v2/working-memory/${ENCODED_WORKSPACE}" \
    -H "Content-Type: application/json" \
    -d "{\"workspace_path\": \"${WORKSPACE}\", \"last_cli\": \"claude_code\"}" \
    > /dev/null 2>&1
```

**Installation** -- Add to `.claude/settings.json`:

```json
{
    "hooks": {
        "session-start": [
            {
                "command": "bash /path/to/claude-memory-system/claude-code-integration/hooks/session-start.sh"
            }
        ]
    }
}
```

---

### 10.2 Codex CLI Hooks

Codex CLI reads `AGENTS.md` for context. Hooks inject context before sessions and import after.

**Pre-Session Hook** -- writes context to `AGENTS.md`:

File: `codex-integration/hooks/pre-session.sh`

```bash
#!/bin/bash
# Inject Memory Hub context into AGENTS.md before Codex starts.

MEMORY_HUB_URL="${MEMORY_HUB_URL:-http://localhost:8765}"
WORKSPACE="$(pwd)"

if ! curl -sf "${MEMORY_HUB_URL}/health" > /dev/null 2>&1; then
    exit 0
fi

# Use the switch preview to generate context
python3 -c "
import urllib.request, json, sys
url = '${MEMORY_HUB_URL}/api/v2/switch/preview?to_cli=codex&workspace_path=${WORKSPACE}'
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.loads(r.read())
        content = data.get('content_preview', '')
        if content:
            print(content)
except:
    pass
" > /tmp/codex-context.md 2>/dev/null

if [ -s /tmp/codex-context.md ]; then
    cp /tmp/codex-context.md AGENTS.md
fi
rm -f /tmp/codex-context.md
```

**Post-Session Hook** -- imports the completed session:

File: `codex-integration/hooks/post-session.sh`

```bash
#!/bin/bash
# Import the latest Codex session after it ends.

MEMORY_HUB_URL="${MEMORY_HUB_URL:-http://localhost:8765}"

curl -sf -X POST "${MEMORY_HUB_URL}/api/v2/import/local" \
    -H "Content-Type: application/json" \
    -d '{"source": "codex", "limit": 1, "auto_summarize": true, "auto_compress": true}' \
    > /dev/null 2>&1
```

**Installation** -- Codex CLI does not have a built-in hook system. Use a shell alias or wrapper:

```bash
# Add to .bashrc or .zshrc
codex-with-memory() {
    bash /path/to/codex-integration/hooks/pre-session.sh
    codex "$@"
    bash /path/to/codex-integration/hooks/post-session.sh
}
alias codex='codex-with-memory'
```

---

### 10.3 Gemini CLI Hooks

Gemini CLI reads `GEMINI.md` for context.

**Pre-Session Hook**:

File: `gemini-integration/hooks/pre-session.sh`

```bash
#!/bin/bash
# Inject Memory Hub context into GEMINI.md before Gemini CLI starts.

MEMORY_HUB_URL="${MEMORY_HUB_URL:-http://localhost:8765}"
WORKSPACE="$(pwd)"

if ! curl -sf "${MEMORY_HUB_URL}/health" > /dev/null 2>&1; then
    exit 0
fi

python3 -c "
import urllib.request, json
url = '${MEMORY_HUB_URL}/api/v2/switch/preview?to_cli=gemini_cli&workspace_path=${WORKSPACE}'
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.loads(r.read())
        content = data.get('content_preview', '')
        if content:
            print(content)
except:
    pass
" > /tmp/gemini-context.md 2>/dev/null

if [ -s /tmp/gemini-context.md ]; then
    cp /tmp/gemini-context.md GEMINI.md
fi
rm -f /tmp/gemini-context.md
```

**Installation** -- Use a shell wrapper:

```bash
# Add to .bashrc or .zshrc
gemini-with-memory() {
    bash /path/to/gemini-integration/hooks/pre-session.sh
    gemini "$@"
}
alias gemini='gemini-with-memory'
```

---

### 10.4 Antigravity

Antigravity integrates via file-based context (brain directory) and protobuf import.

**Context Injection** -- Write to Antigravity's brain directory:

```bash
#!/bin/bash
# Inject Memory Hub context for Antigravity.
MEMORY_HUB_URL="${MEMORY_HUB_URL:-http://localhost:8765}"
WORKSPACE="$(pwd)"
BRAIN_DIR="$HOME/.gemini/antigravity/brain"

if ! curl -sf "${MEMORY_HUB_URL}/health" > /dev/null 2>&1; then
    exit 0
fi

mkdir -p "$BRAIN_DIR"
python3 -c "
import urllib.request, json
url = '${MEMORY_HUB_URL}/api/v2/switch/preview?to_cli=antigravity&workspace_path=${WORKSPACE}'
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.loads(r.read())
        content = data.get('content_preview', '')
        if content:
            print(content)
except:
    pass
" > "${BRAIN_DIR}/memory-hub-context.md" 2>/dev/null
```

**Import** -- Antigravity conversations are auto-imported via the protobuf importer in `local_importer.py`:

```bash
memory-hub import --source antigravity --limit 20
```

---

### 10.5 Quick Setup (All CLIs)

For the fastest setup, use the `memory-hub switch` command instead of hooks:

```bash
# Before starting any CLI, just run:
memory-hub switch --to codex
codex

# Or:
memory-hub switch --to gemini_cli
gemini

# After finishing:
memory-hub import --source all --limit 5
```

This is the simplest approach and works immediately without any hook configuration.

---

## 11. Error Handling

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid parameters, unsupported CLI, etc.) |
| 404 | Resource not found |
| 500 | Internal server error |

### Error Response Format

```json
{
    "detail": "Human-readable error message"
}
```

### Graceful Degradation

- If Memory Hub is not running, all hooks and CLI tool exit silently (exit code 0)
- If AI provider is unavailable, summaries fall back to rule-based extraction
- If a conversation already exists (duplicate hash), the existing ID is returned without error

---

## 12. Data Models

### MessageInput

```json
{
    "role": "string (required): user | assistant | system | tool",
    "content": "string (required): Full message text",
    "content_type": "string (default: text): text | tool_use | tool_result | image | thinking",
    "metadata": "object (default: {}): Tool name, file paths, etc."
}
```

### WorkingMemoryInput

```json
{
    "workspace_path": "string (required): Absolute path",
    "active_task": "string: Current task description",
    "current_plan": "array[string]: Ordered steps",
    "progress": "array[string]: Completed steps",
    "open_issues": "array[string]: Blockers, TODOs",
    "recent_changes": "string: Recent code changes summary",
    "last_cli": "string: Last CLI used",
    "last_session_id": "string: Last conversation UUID",
    "context_snippet": "string: Key conversation excerpt"
}
```

### SwitchInput

```json
{
    "from_cli": "string: Source CLI (optional, for logging)",
    "to_cli": "string (required): claude_code | codex | gemini_cli | antigravity",
    "workspace_path": "string (required): Absolute workspace path",
    "from_session_id": "string: Capture state from this session",
    "token_budget": "int: Override default token budget",
    "include_archive_turns": "int: Override archive turn count"
}
```

### ConversationV2Input

See [POST /api/v2/conversations](#post-apiv2conversations) for the full schema.

### Content Compression Rules

Messages are auto-compressed at import time. The `compressed` field in `archive_messages` stores the compressed version. Compression rules:

| Content Type | Detection | Compressed Form |
|-------------|-----------|-----------------|
| Tool: Read | `content_type: tool_use` + Read pattern | `[Read: {path}, {lines} lines]` |
| Tool: Bash | `content_type: tool_use` + Bash pattern | `[Bash: {cmd} -> {status}]` |
| Tool: Edit | `content_type: tool_use` + Edit pattern | `[Edit: {file}]` |
| Tool: Search | `content_type: tool_use` + Grep pattern | `[Search: "{query}" -> {n} matches]` |
| Tool: Write | `content_type: tool_use` + Write pattern | `[Write: {path}, {lines} lines]` |
| Long code (>20 lines) | Triple backtick blocks | First 5 + `...{n} omitted` + last 3 lines |
| Error stacks (>10 lines) | Traceback/Error pattern | First line + root cause + last line |
| Thinking blocks | `<thinking>` tags | `[Thinking: {first_sentence}...]` |
| Large tool results (>2000 chars) | Length check | Truncated to 500 chars |

---

_Memory Hub V2 API Reference -- Complete documentation for the three-layer memory architecture_
