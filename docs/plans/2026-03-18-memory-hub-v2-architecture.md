# Memory Hub V2 -- Complete Architecture Design

**Date**: 2026-03-18
**Status**: Architecture Approved
**Author**: Architect Agent
**Predecessor**: [2026-03-17 V2 Design Doc](./2026-03-17-memory-hub-v2-design.md) (builds on its three-layer memory model and CLI switching concept)

---

## 1. Executive Summary

Memory Hub V2 transforms the existing single-purpose conversation logger into a **cross-CLI memory center** with three core capabilities:

1. **Full Conversation Sync** -- capture and store complete conversations from all platforms (Claude Code, Codex CLI, Gemini CLI, Antigravity, browser-based AI chats)
2. **CLI Quick Switch** -- when one CLI's quota runs out, switch to another CLI with full context continuity (no re-briefing)
3. **Memory CRUD** -- manage memories and conversations from a unified Web UI and CLI tool

---

## 2. Current State Analysis

### 2.1 What Exists

| Component | File(s) | Status |
|-----------|---------|--------|
| FastAPI backend | `backend/main.py` (1961 LOC) | Working, monolithic |
| SQLite database | `backend/database.py` | Single `conversations` table + `preferences` + lineage/usage |
| ChromaDB vector search | `backend/vector_store.py` | Hash-based local embeddings |
| Local importers | `backend/local_importer.py` | Supports codex, claude_code, gemini_cli, antigravity |
| Client exports | `backend/client_exports.py` | Supports claude_code (CLAUDE.md), codex (AGENTS.md), gemini_cli (GEMINI.md) |
| AI analyzer | `backend/ai_analyzer.py` + `ai_providers.py` | Multi-provider summarization |
| Browser extension | `browser-extension/` | Chrome extension for Claude/ChatGPT/Gemini/Grok/DeepSeek |
| Vue.js Web UI | `web-ui/` | Conversations list, detail, search, settings, memories |
| Memory consolidation | `backend/memory_consolidation.py` + `scheduler.py` | Forgetting curve, daily consolidation |
| Preference learning | `backend/preference_learning.py` | Pattern-based preference extraction |
| Backup/restore | `backend/backup_export.py` | Scheduled backup bundles |

### 2.2 Key Gaps for V2

1. **No structured message storage** -- `full_content` is a flat text blob (`"user: ...\n\nassistant: ..."`)
2. **No working memory** -- no concept of "current task state" or "what was I doing"
3. **No switch command** -- cannot one-click migrate context to another CLI
4. **No conversation-level message API** -- cannot browse individual messages in a conversation
5. **Antigravity export missing** -- `client_exports.py` has no antigravity profile
6. **No hook system for Codex/Gemini CLI** -- only Claude Code has `session-start.sh`
7. **Content compression not implemented** -- the v1 design doc describes rules but no code exists

---

## 3. Three-Layer Memory Architecture

Inheriting the MemGPT-inspired design from the previous design doc, refined for implementation.

### 3.1 Architecture Overview

```
                    +-----------------------------------------+
                    |           Memory Hub V2 Service          |
                    |                                         |
                    |   +----------+  +--------+  +--------+  |
                    |   | Archive  |  |  Core  |  |Working |  |
                    |   | Layer    |  | Layer  |  | Layer  |  |
                    |   | (full   |  | (facts |  | (task  |  |
                    |   |  convos) |  |  prefs) |  |  state) |  |
                    |   +----+-----+  +---+----+  +---+----+  |
                    |        |            |           |        |
                    |        v            v           v        |
                    |   +----------------------------------+   |
                    |   |     Context Assembly Engine       |   |
                    |   |  (compress + adapt per CLI)      |   |
                    |   +----------------------------------+   |
                    |        |                                 |
                    |   +----------------------------------+   |
                    |   |     Export Adapter Layer          |   |
                    |   |  CLAUDE.md | AGENTS.md | GEMINI  |   |
                    |   +----------------------------------+   |
                    +---------+-------------------+-----------+
                              |                   |
                   Ingest     |                   |  Inject
                              v                   v
        +----------------------------------------------------------+
        | Claude Code | Codex CLI | Gemini CLI | Antigravity | Web |
        +----------------------------------------------------------+
```

### 3.2 Archive Layer (Full Conversations)

Stores **complete conversation transcripts** in structured JSON format. This is the "source of truth".

**New table: `archive_conversations`**

```sql
CREATE TABLE archive_conversations (
    id              TEXT PRIMARY KEY,           -- UUID
    platform        TEXT NOT NULL,              -- claude_code | codex | gemini_cli | antigravity | claude_web | chatgpt | gemini_web | grok | deepseek
    session_id      TEXT,                       -- Original session ID from the CLI/platform
    workspace_path  TEXT,                       -- Working directory (for code CLIs)
    started_at      TEXT NOT NULL,              -- Session start time (ISO 8601)
    ended_at        TEXT,                       -- Session end time
    message_count   INTEGER DEFAULT 0,          -- Number of messages
    token_estimate  INTEGER DEFAULT 0,          -- Estimated total tokens
    summary         TEXT,                       -- AI-generated or derived summary
    summary_source  TEXT DEFAULT 'fallback',    -- 'ai' | 'imported' | 'fallback'
    importance      INTEGER DEFAULT 5,          -- 1-10 importance score
    provider        TEXT,                       -- AI provider (anthropic/openai/google/xai/deepseek)
    model           TEXT,                       -- Model name
    assistant_label TEXT,                       -- Display name for the assistant
    source_path     TEXT,                       -- Original file path (for imported sessions)
    source_fingerprint TEXT,                    -- File fingerprint for dedup
    content_hash    TEXT UNIQUE,                -- SHA-256 of serialized messages for dedup
    metadata        TEXT DEFAULT '{}',          -- JSON: extensible metadata
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_archive_platform_time ON archive_conversations(platform, started_at);
CREATE INDEX idx_archive_workspace ON archive_conversations(workspace_path);
CREATE INDEX idx_archive_hash ON archive_conversations(content_hash);
CREATE INDEX idx_archive_session ON archive_conversations(session_id);
```

**New table: `archive_messages`** (normalized message storage)

```sql
CREATE TABLE archive_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,              -- FK to archive_conversations.id
    ordinal         INTEGER NOT NULL,           -- Message position (0-based)
    role            TEXT NOT NULL,              -- 'user' | 'assistant' | 'system' | 'tool'
    content         TEXT NOT NULL,              -- Full message content
    content_type    TEXT DEFAULT 'text',        -- 'text' | 'tool_use' | 'tool_result' | 'image' | 'thinking'
    compressed      TEXT,                       -- Rule-compressed version (NULL = use content)
    token_estimate  INTEGER DEFAULT 0,          -- Estimated tokens for this message
    metadata        TEXT DEFAULT '{}',          -- JSON: tool name, file paths, etc.
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (conversation_id) REFERENCES archive_conversations(id) ON DELETE CASCADE
);

CREATE INDEX idx_messages_conversation ON archive_messages(conversation_id, ordinal);
CREATE INDEX idx_messages_role ON archive_messages(conversation_id, role);
```

**Migration strategy**: The existing `conversations` table maps 1:1 to `archive_conversations`. Migration script will:
1. Copy rows from `conversations` to `archive_conversations`
2. Parse `full_content` (using the existing `"role: content"` format) into `archive_messages` rows
3. Keep the old table as `conversations_v1_backup` for safety
4. Update all foreign keys (topics, decisions, conversation_relations, preference_sources)

### 3.3 Core Layer (Structured Knowledge)

Reuses the existing `preferences` table, extended. Core memories are **always available** for injection.

**Existing table `preferences` -- renamed conceptually to `core_memories`** (no table rename needed, just API/UI renaming):

```sql
-- Existing columns preserved:
--   id, category, key, value, confidence, priority, client_rules, status, last_updated

-- New columns to add:
ALTER TABLE preferences ADD COLUMN pinned INTEGER DEFAULT 0;          -- User-pinned (never decays)
ALTER TABLE preferences ADD COLUMN tags TEXT DEFAULT '[]';            -- JSON array of tags
ALTER TABLE preferences ADD COLUMN workspace_scope TEXT;              -- NULL = global, else workspace path
ALTER TABLE preferences ADD COLUMN accessed_at TEXT;                  -- Last injection/view time (for decay)
ALTER TABLE preferences ADD COLUMN source_conversation_ids TEXT DEFAULT '[]';  -- JSON array linking to archive
```

**Category taxonomy** (expanding current: identity, preference, workflow, avoid):

| Category | Description | Injection Priority |
|----------|-------------|-------------------|
| `identity` | Who the user is, their role | Always inject |
| `preference` | Coding style, tool preferences | High |
| `workflow` | How they like to work | High |
| `avoid` | Things NOT to do | High |
| `decision` | Key architectural/technical decisions | Medium |
| `fact` | Project facts, domain knowledge | Medium |
| `task_state` | Current task progress (overlaps with working layer) | Context-dependent |
| `codebase` | Codebase conventions, patterns | Context-dependent |

### 3.4 Working Layer (Active Task Context)

Tracks the **current state** of work in each workspace. This is what enables seamless CLI switching.

**New table: `working_memory`**

```sql
CREATE TABLE working_memory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_path  TEXT NOT NULL UNIQUE,        -- One working memory per project
    active_task     TEXT,                        -- Current task description
    current_plan    TEXT,                        -- JSON: ordered step list with status
    progress        TEXT,                        -- JSON: completed steps summary
    open_issues     TEXT,                        -- JSON: blockers, questions, TODOs
    recent_changes  TEXT,                        -- Summary of recent code modifications
    last_cli        TEXT,                        -- Last CLI used (for switch awareness)
    last_session_id TEXT,                        -- FK to archive_conversations.id
    context_snippet TEXT,                        -- Last N relevant conversation turns (pre-compressed)
    switch_count    INTEGER DEFAULT 0,           -- How many times we've switched CLIs for this workspace
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_working_workspace ON working_memory(workspace_path);
```

**Working memory lifecycle**:
1. **Created** when a CLI session starts in a new workspace
2. **Updated** at session end (hook captures task state, plan progress, recent changes)
3. **Read** at session start -- injected into the new CLI's context
4. **Cleared** when user marks task as complete (via Web UI or CLI command)

---

## 4. Complete Conversation Sync Engine

### 4.1 Ingest Pipeline

```
Source (CLI/Browser) --> Ingest API --> Parser --> Dedup --> Store --> Index --> Compress --> Summarize
```

Each step:

1. **Ingest API** (`POST /api/v2/conversations`): Accepts raw conversation data
2. **Parser**: Normalizes platform-specific formats into `archive_messages` rows
3. **Dedup**: `content_hash` check prevents duplicate imports
4. **Store**: Writes to `archive_conversations` + `archive_messages`
5. **Index**: Upserts into ChromaDB vector store
6. **Compress**: Applies rule-based compression to create `compressed` field per message
7. **Summarize**: AI-generates summary (async, non-blocking)

### 4.2 Platform-Specific Importers

| Platform | Source | Capture Method | Message Format |
|----------|--------|---------------|----------------|
| Claude Code | `~/.claude/projects/*/` | Session-end hook + file import | JSONL with tool_use blocks |
| Codex CLI | `~/.codex/sessions/` | File import | JSON with input/output messages |
| Gemini CLI | `~/.gemini/tmp/` | File import | JSON with parts array |
| Antigravity | `~/.gemini/antigravity/conversations/` | Protobuf import + gRPC | Protobuf messages |
| Claude Web | Browser extension | Manual sync button | DOM-extracted messages |
| ChatGPT | Browser extension | Manual sync button | DOM-extracted messages |
| Gemini Web | Browser extension | Manual sync button | DOM-extracted messages |
| Grok | Browser extension | Manual sync button | DOM-extracted messages |
| DeepSeek | Browser extension | Manual sync button | DOM-extracted messages |

### 4.3 New Ingest API Contract

```
POST /api/v2/conversations
{
    "platform": "claude_code",
    "session_id": "abc-123",
    "workspace_path": "/path/to/project",
    "started_at": "2026-03-18T10:00:00Z",
    "ended_at": "2026-03-18T10:30:00Z",
    "provider": "anthropic",
    "model": "claude-opus-4-6",
    "messages": [
        {
            "role": "user",
            "content": "Fix the auth bug",
            "content_type": "text"
        },
        {
            "role": "assistant",
            "content": "I'll investigate the auth module...",
            "content_type": "text"
        },
        {
            "role": "assistant",
            "content": "<tool_use>Read file: src/auth.py</tool_use>",
            "content_type": "tool_use",
            "metadata": {"tool": "Read", "path": "src/auth.py"}
        }
    ],
    "working_state": {                       // Optional: auto-capture working memory
        "active_task": "Fix auth token refresh bug",
        "plan": ["Investigate", "Fix", "Test"],
        "progress": ["Investigated - found race condition in token refresh"],
        "open_issues": ["Need to add retry logic"]
    },
    "metadata": {}
}
```

---

## 5. CLI Quick Switch Mechanism

### 5.1 Switch Flow

```
User: "Quota exhausted on Claude Code, switch to Codex"
                    |
                    v
    +-------------------------------+
    | 1. Capture current state      |
    |    - Save working memory      |
    |    - Mark session as switched  |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | 2. Assemble context           |
    |    - Working layer (full)     |
    |    - Core layer (filtered)    |
    |    - Archive layer (budget)   |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | 3. Adapt for target CLI       |
    |    - Format as AGENTS.md etc  |
    |    - Respect token budget     |
    |    - Apply compression rules  |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | 4. Inject into target CLI     |
    |    - Write context file       |
    |    - Open CLI in workspace    |
    +-------------------------------+
```

### 5.2 Switch API

```
POST /api/v2/switch
{
    "from_cli": "claude_code",          // Optional: source CLI
    "to_cli": "codex",                  // Required: target CLI
    "workspace_path": "/path/to/project",
    "from_session_id": "abc-123",       // Optional: capture state from this session
    "token_budget": null,               // Optional: override default budget
    "include_archive_turns": null       // Optional: how many recent conversation turns to include
}

Response:
{
    "status": "ok",
    "target_file": "/path/to/project/AGENTS.md",
    "working_memory": { ... },
    "core_memories_injected": 12,
    "archive_turns_injected": 3,
    "total_tokens_estimated": 45000,
    "switch_count": 2
}
```

### 5.3 CLI Tool: `memory-hub`

A standalone Python CLI that wraps the switch API:

```bash
# Quick switch
memory-hub switch --to codex
memory-hub switch --to gemini_cli --workspace /path/to/project

# Manual state capture
memory-hub save-state --task "Implementing auth flow" --plan "1. Fix token refresh 2. Add tests"

# View current working memory
memory-hub status

# Import latest sessions
memory-hub import --source all --limit 10

# Search conversations
memory-hub search "auth token bug"
```

### 5.4 Context Budget Strategy

The v1 design doc defined token budgets per CLI. Here is the refined strategy:

```
Token budget allocation per CLI:

Claude Code (~200K system context):
    Working layer:    1,000-3,000 tokens (always full)
    Core layer:       2,000-5,000 tokens (top N by priority+relevance)
    Archive excerpt:  5,000-20,000 tokens (recent compressed turns)
    Total injection:  ~8,000-28,000 tokens (leaves plenty for conversation)

Codex CLI (~128K):
    Working layer:    1,000-2,000 tokens
    Core layer:       2,000-4,000 tokens
    Archive excerpt:  3,000-10,000 tokens
    Total injection:  ~6,000-16,000 tokens

Gemini CLI (~1M):
    Working layer:    1,000-3,000 tokens
    Core layer:       3,000-8,000 tokens
    Archive excerpt:  20,000-100,000 tokens (can include much more history)
    Total injection:  ~24,000-111,000 tokens

Antigravity (~128K, TBD):
    Working layer:    1,000-2,000 tokens
    Core layer:       2,000-4,000 tokens
    Archive excerpt:  3,000-10,000 tokens
    Total injection:  ~6,000-16,000 tokens
```

### 5.5 Context Assembly Algorithm

```python
def assemble_switch_context(workspace_path, target_cli, token_budget=None):
    """
    Assemble context for CLI switch injection.
    Returns formatted markdown ready for the target CLI's context file.
    """
    profile = get_export_profile(target_cli)
    budget = token_budget or DEFAULT_BUDGETS[target_cli]

    # 1. Working memory (always injected in full)
    working = get_working_memory(workspace_path)
    working_section = format_working_memory(working)
    remaining_budget = budget - estimate_tokens(working_section)

    # 2. Core memories (filtered by workspace + priority)
    all_core = get_core_memories(workspace_scope=workspace_path)
    global_core = get_core_memories(workspace_scope=None)  # Global memories
    merged_core = deduplicate(all_core + global_core)

    # Sort by: pinned first, then priority DESC, then relevance to working task
    sorted_core = sort_by_relevance(merged_core, working.active_task, profile)
    core_section = ""
    for memory in sorted_core:
        candidate = format_core_memory(memory)
        if estimate_tokens(core_section + candidate) > remaining_budget * 0.4:
            break
        core_section += candidate

    remaining_budget -= estimate_tokens(core_section)

    # 3. Archive excerpt (compressed recent turns)
    if remaining_budget > 1000:
        recent_sessions = get_recent_archive_sessions(
            workspace_path=workspace_path,
            limit=5
        )
        archive_section = ""
        for session in recent_sessions:
            compressed = get_compressed_messages(session.id)
            candidate = format_archive_excerpt(session, compressed)
            if estimate_tokens(archive_section + candidate) > remaining_budget:
                break
            archive_section += candidate
    else:
        archive_section = ""

    # 4. Assemble final document
    return format_for_cli(profile, working_section, core_section, archive_section)
```

---

## 6. Content Compression System

### 6.1 Rule-Based Compression (covers ~90% of content)

Applied at import time, stored in `archive_messages.compressed`.

| Content Type | Detection Pattern | Compression Rule |
|-------------|-------------------|-----------------|
| Tool: Read | `tool_use` + `Read` | `[Read: {path}, {lines} lines]` |
| Tool: Bash | `tool_use` + `Bash` | `[Bash: {cmd_short} -> {exit_code}]` |
| Tool: Edit | `tool_use` + `Edit` | `[Edit {file}: {description}]` |
| Tool: Grep/Search | `tool_use` + `Grep` | `[Search "{query}" -> {n} matches]` |
| Tool: Write | `tool_use` + `Write` | `[Write: {path}, {lines} lines]` |
| Tool: WebSearch | `tool_use` + `WebSearch` | `[Web: "{query}" -> {summary}]` |
| Tool: Agent | `tool_use` + `Agent` | `[SubAgent: {task} -> {result}]` |
| Long code blocks | `` ``` `` > 20 lines | First 5 lines + `// ...{n} lines omitted` + last 3 lines |
| Error stacks | `Traceback\|Error:` > 10 lines | First line + root cause + last line |
| Thinking blocks | `<thinking>` | `[Thinking: {first_sentence}...]` |
| Large tool results | Tool result > 2000 chars | Truncate to 500 chars + `[...truncated]` |

### 6.2 AI-Assisted Compression (remaining ~10%)

For messages that don't match rules but are very long (>2000 tokens), call the AI summarizer:

```python
async def ai_compress_message(content: str, context: str) -> str:
    """Ask AI to compress a message while preserving key decisions and actions."""
    prompt = f"""Compress this conversation message to ~20% of its length.
    Preserve: decisions, action items, errors, key technical details.
    Remove: verbose explanations, repeated context, filler.
    Context: {context[:500]}
    Message: {content}"""
    return await analyzer.generate_completion(prompt)
```

---

## 7. API Design

### 7.1 New V2 Endpoints

All new endpoints are under `/api/v2/` prefix. V1 endpoints remain unchanged for backward compatibility.

#### Conversations (Archive Layer)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v2/conversations` | Ingest a full conversation with structured messages |
| `GET` | `/api/v2/conversations` | List conversations (paginated, filtered) |
| `GET` | `/api/v2/conversations/{id}` | Get conversation with messages |
| `GET` | `/api/v2/conversations/{id}/messages` | Get messages only (paginated) |
| `DELETE` | `/api/v2/conversations/{id}` | Delete conversation and its messages |
| `POST` | `/api/v2/conversations/{id}/summarize` | Re-generate AI summary |
| `GET` | `/api/v2/conversations/{id}/compressed` | Get compressed message view |

#### Working Memory

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v2/working-memory/{workspace_path}` | Get working memory for a workspace |
| `PUT` | `/api/v2/working-memory/{workspace_path}` | Update working memory (upsert) |
| `DELETE` | `/api/v2/working-memory/{workspace_path}` | Clear working memory |
| `GET` | `/api/v2/working-memory` | List all active working memories |

#### Core Memories

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v2/core-memories` | List core memories (with filtering) |
| `POST` | `/api/v2/core-memories` | Create a core memory |
| `PUT` | `/api/v2/core-memories/{id}` | Update a core memory |
| `DELETE` | `/api/v2/core-memories/{id}` | Delete a core memory |
| `POST` | `/api/v2/core-memories/{id}/pin` | Pin/unpin a core memory |
| `POST` | `/api/v2/core-memories/extract/{conversation_id}` | Extract memories from a conversation |

#### Switch

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v2/switch` | Execute CLI switch with context injection |
| `GET` | `/api/v2/switch/preview` | Preview what would be injected (dry run) |
| `GET` | `/api/v2/switch/history` | List recent switches |

#### Import/Export

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v2/import/local` | Import local CLI sessions (enhanced) |
| `POST` | `/api/v2/import/browser` | Import from browser extension |
| `GET` | `/api/v2/export/clients` | List supported export targets |
| `POST` | `/api/v2/export/{client}` | Generate export for a specific CLI |
| `POST` | `/api/v2/export/{client}/apply` | Write export to workspace |

### 7.2 V2 Conversation Ingest Contract

```json
// POST /api/v2/conversations
// Request:
{
    "platform": "claude_code",
    "session_id": "session-abc-123",
    "workspace_path": "D:\\pythonproject\\my-project",
    "started_at": "2026-03-18T10:00:00Z",
    "ended_at": "2026-03-18T10:45:00Z",
    "provider": "anthropic",
    "model": "claude-opus-4-6",
    "messages": [
        {"role": "user", "content": "...", "content_type": "text"},
        {"role": "assistant", "content": "...", "content_type": "text"},
        {"role": "assistant", "content": "...", "content_type": "tool_use", "metadata": {"tool": "Read"}}
    ],
    "working_state": {
        "active_task": "Fix auth bug",
        "plan": ["Step 1", "Step 2"],
        "progress": ["Step 1 done"],
        "open_issues": ["Need test coverage"]
    },
    "summary": null,
    "metadata": {}
}

// Response:
{
    "status": "ok",
    "conversation_id": "uuid-...",
    "message_count": 15,
    "token_estimate": 12500,
    "summary": "Fixed auth token refresh race condition...",
    "working_memory_updated": true
}
```

### 7.3 V2 Switch Contract

```json
// POST /api/v2/switch
// Request:
{
    "to_cli": "codex",
    "workspace_path": "D:\\pythonproject\\my-project",
    "from_session_id": "session-abc-123",
    "token_budget": null
}

// Response:
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

---

## 8. Database Schema Upgrade Plan

### 8.1 Migration Steps

```python
MIGRATION_V2 = [
    # Step 1: Create new tables
    """
    CREATE TABLE IF NOT EXISTS archive_conversations ( ... );
    CREATE TABLE IF NOT EXISTS archive_messages ( ... );
    CREATE TABLE IF NOT EXISTS working_memory ( ... );
    """,

    # Step 2: Migrate existing data
    """
    INSERT INTO archive_conversations (id, platform, started_at, summary, ...)
    SELECT id, platform, timestamp, summary, ...
    FROM conversations;
    """,

    # Step 3: Parse full_content into archive_messages
    # (Done in Python, not SQL -- needs the role:content parser)

    # Step 4: Add new columns to preferences
    """
    ALTER TABLE preferences ADD COLUMN pinned INTEGER DEFAULT 0;
    ALTER TABLE preferences ADD COLUMN tags TEXT DEFAULT '[]';
    ALTER TABLE preferences ADD COLUMN workspace_scope TEXT;
    ALTER TABLE preferences ADD COLUMN accessed_at TEXT;
    """,

    # Step 5: Create schema version tracker
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
        description TEXT
    );
    INSERT INTO schema_version (version, description) VALUES (2, 'V2 three-layer memory architecture');
    """,
]
```

### 8.2 Backward Compatibility

- V1 API endpoints continue to work, reading from `archive_conversations` via a compatibility view
- V1 `full_content` field is reconstructed on-the-fly from `archive_messages` when needed
- The `conversations` table is renamed to `conversations_v1_backup` after successful migration

---

## 9. Hook System for All CLIs

### 9.1 Claude Code (existing, enhanced)

```bash
# claude-code-integration/hooks/session-start.sh (enhanced)
# On session start: inject context from Memory Hub
curl -s "http://localhost:8765/api/v2/switch/preview?to_cli=claude_code&workspace_path=$(pwd)" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('content_preview',''))" \
  > .claude/CLAUDE.md.memory-hub

# claude-code-integration/hooks/session-end.sh (new)
# On session end: capture working state
curl -s -X POST "http://localhost:8765/api/v2/working-memory/$(pwd)" \
  -H "Content-Type: application/json" \
  -d '{"last_cli": "claude_code", "last_session_id": "'"$SESSION_ID"'"}'
```

### 9.2 Codex CLI

Codex CLI supports `AGENTS.md` as its context file. Hook integration:

```bash
# codex-integration/hooks/pre-session.sh
# Write context to AGENTS.md before Codex starts
memory-hub switch --to codex --workspace "$(pwd)" --quiet

# codex-integration/hooks/post-session.sh
# Import the session after it ends
memory-hub import --source codex --limit 1
```

### 9.3 Gemini CLI

Gemini CLI reads `GEMINI.md`. Hook integration:

```bash
# gemini-integration/hooks/pre-session.sh
memory-hub switch --to gemini_cli --workspace "$(pwd)" --quiet
```

### 9.4 Antigravity

Antigravity has a more complex integration (gRPC + file-based). The existing protobuf importer handles ingest. For injection, we write to Antigravity's brain directory:

```bash
# antigravity-integration/inject.sh
memory-hub switch --to antigravity --workspace "$(pwd)" --quiet
# Antigravity reads from ~/.gemini/antigravity/brain/ (markdown files)
```

---

## 10. Export Adapter Updates

### 10.1 New `antigravity` Export Profile

```python
CLIENT_EXPORT_PROFILES["antigravity"] = ClientExportProfile(
    client_id="antigravity",
    display_name="Antigravity",
    target_relpath=".antigravity/context.md",  # TBD: confirm actual path
    filename="context.md",
    format_hint="antigravity_md",
    description="Write resume context for Antigravity sessions.",
    preferred_categories=("identity", "workflow", "decision"),
    category_bonus={"identity": 3.0, "workflow": 3.0, "decision": 2.5, "preference": 2.0},
    default_limit=10,
    strategy_summary="Prefer identity, workflow patterns, and key decisions for task continuity.",
)
```

### 10.2 Enhanced Export Format

The V2 export format includes all three memory layers:

```markdown
# Resume Context: {task_description}

_Switched from {from_cli} on {timestamp}_
_Switch #{switch_count} for this workspace_

## Current Task (Working Memory)

**Task**: {active_task}
**Progress**: {completed_steps}
**Open Issues**: {open_issues}
**Recent Changes**: {recent_changes}

## Key Context (Core Memory)

### identity
- **role**: Senior developer working on auth system

### decision
- **auth_design**: Using JWT with rotating refresh tokens

### preference
- **code_style**: Prefer explicit error handling over try/catch

## Recent Conversation (Archive Excerpt)

### Session: {timestamp} ({from_cli})
User: Fix the auth token refresh bug
Assistant: I found a race condition in token_refresh()...
[Edit src/auth.py: Added mutex lock around refresh logic]
[Bash: pytest tests/test_auth.py -> 5 passed]
User: Good, now add retry logic
Assistant: [working on retry implementation]

---
_Context assembled by Memory Hub V2_
```

---

## 11. Implementation Priorities

### Phase V2.1: Foundation (Critical Path)

1. **Database migration** -- Create `archive_conversations`, `archive_messages`, `working_memory` tables
2. **V2 ingest API** -- `POST /api/v2/conversations` with structured messages
3. **Content compression engine** -- Rule-based compression for tool_use, code blocks, etc.
4. **Data migration script** -- Migrate V1 `conversations` to V2 archive tables

### Phase V2.2: Switch Engine

5. **Context assembly engine** -- Assemble three-layer context with token budgeting
6. **Switch API** -- `POST /api/v2/switch` endpoint
7. **`memory-hub` CLI tool** -- Python CLI wrapping the switch API
8. **Hook scripts** -- Pre/post session hooks for all 4 CLIs

### Phase V2.3: Enhanced CRUD + UI

9. **Working memory API** -- Full CRUD for working memory
10. **Core memory enhancements** -- Pinning, tagging, workspace scoping
11. **Web UI updates** -- Three-layer memory view, switch panel, message browser
12. **Antigravity export profile** -- Complete the export adapter

### Phase V2.4: Intelligence

13. **AI compression** -- Fallback AI compression for messages that don't match rules
14. **Smart memory extraction** -- AI-powered extraction of core memories from archive
15. **Relevance ranking** -- Better scoring for core memory selection during switch
16. **Cross-session linking** -- Automatically link related sessions across CLIs

---

## 12. File Changes Summary

```
backend/
    database.py          [MODIFY] Add V2 tables, migration logic
    database_v2.py       [NEW]    V2 database layer with message-level operations
    models_v2.py         [NEW]    V2 Pydantic models for API contracts
    main.py              [MODIFY] Add /api/v2/* endpoints
    compression.py       [NEW]    Rule-based + AI compression engine
    context_assembler.py [NEW]    Three-layer context assembly
    switch_engine.py     [NEW]    CLI switch orchestration
    client_exports.py    [MODIFY] Add antigravity profile, V2 export format
    local_importer.py    [MODIFY] Output structured messages instead of flat text

cli/
    memory_hub.py        [NEW]    CLI tool entry point
    commands/
        switch.py        [NEW]    switch command
        import_cmd.py    [NEW]    import command
        status.py        [NEW]    status command
        search.py        [NEW]    search command

claude-code-integration/hooks/
    session-end.sh       [NEW]    Capture working state on session end

codex-integration/
    hooks/
        pre-session.sh   [NEW]    Inject context before Codex session
        post-session.sh  [NEW]    Import session after Codex ends

gemini-integration/
    hooks/
        pre-session.sh   [NEW]    Inject context before Gemini CLI session

web-ui/src/
    views/
        WorkingMemory.vue   [NEW]    Working memory management view
        SwitchPanel.vue     [NEW]    CLI switch interface
        MessageBrowser.vue  [NEW]    Individual message browsing
    components/
        MemoryLayerTabs.vue [NEW]    Three-layer tab navigation
```

---

## 13. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Data migration corrupts existing conversations | Keep `conversations_v1_backup` table; run migration in transaction with rollback |
| Token estimation inaccurate | Use conservative estimates (4 chars/token for English, 2 chars/token for Chinese); allow manual budget override |
| CLI hook breaks user's workflow | All hooks are opt-in; graceful failure (if Memory Hub is down, hook silently skips) |
| Large conversations exceed SQLite performance | Archive messages use integer PK with covering indexes; consider WAL mode for concurrent reads |
| Context injection too large | Hard cap per CLI; truncation strategy preserves most recent + highest priority content |

---

## 14. Success Metrics

1. **Switch latency**: < 3 seconds from `memory-hub switch` to context file written
2. **Context quality**: After switch, new CLI can continue task without user re-explaining (manual validation)
3. **Import coverage**: All 4 CLI sources import with structured messages (not flat text)
4. **Compression ratio**: Tool-heavy conversations compressed to < 30% of original tokens
5. **Zero data loss**: V1 to V2 migration preserves 100% of existing conversations

---

_Document version: 1.0_
_Architecture design for Memory Hub V2 -- enabling seamless context continuity across AI CLIs_
