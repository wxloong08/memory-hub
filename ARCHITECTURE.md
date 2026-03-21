# Claude Cross-Platform Memory System - Architecture

## System Overview

The Claude Cross-Platform Memory System enables seamless context continuity across AI CLI platforms (Claude Code, Codex CLI, Gemini CLI, Antigravity) and browser-based AI chats by automatically capturing, processing, and injecting conversation context.

**Version 2** introduces a **three-layer memory architecture**, a **CLI quick switch mechanism**, and **full structured conversation storage** — transforming the system from a single-purpose conversation logger into a cross-CLI memory center.

---

## V2 Three-Layer Memory Architecture

Inspired by MemGPT's virtual context management and Mem0's extract-consolidate-retrieve pipeline (see [Research Survey](docs/research/2026-03-18-memory-context-engineering-survey.md)), V2 organizes memory into three distinct layers:

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

### Layer 1: Archive Layer (Full Conversations)

Stores **complete conversation transcripts** in structured JSON format. This is the "source of truth" for all conversation history.

**Tables**: `archive_conversations` + `archive_messages`

- **archive_conversations**: One row per conversation session (UUID, platform, workspace, timestamps, summary, importance, provider/model metadata, content hash for dedup)
- **archive_messages**: Normalized message storage with ordinal position, role, content, content_type (text/tool_use/tool_result/image/thinking), compressed variant, and token estimates

**Key capabilities**:
- Content-hash-based deduplication prevents duplicate imports
- Per-message compression stores compressed versions alongside originals
- Supports all platforms: claude_code, codex, gemini_cli, antigravity, claude_web, chatgpt, gemini_web, grok, deepseek

### Layer 2: Core Layer (Structured Knowledge)

Reuses the existing `preferences` table, conceptually renamed to "core memories". These are **always-available** facts, decisions, and preferences that should be injected into every CLI session.

**Extended columns**: `pinned` (never decays), `tags` (JSON array), `workspace_scope` (NULL = global), `accessed_at` (for decay tracking), `source_conversation_ids` (links to archive)

**Category taxonomy**:

| Category | Description | Injection Priority |
|----------|-------------|-------------------|
| `identity` | Who the user is, their role | Always inject |
| `preference` | Coding style, tool preferences | High |
| `workflow` | How they like to work | High |
| `avoid` | Things NOT to do | High |
| `decision` | Key architectural/technical decisions | Medium |
| `fact` | Project facts, domain knowledge | Medium |
| `task_state` | Current task progress | Context-dependent |
| `codebase` | Codebase conventions, patterns | Context-dependent |

### Layer 3: Working Layer (Active Task Context)

Tracks the **current state** of work in each workspace. This is what enables seamless CLI switching.

**Table**: `working_memory` (one row per workspace)

- `active_task`: Current task description
- `current_plan`: JSON ordered step list with status
- `progress`: JSON completed steps summary
- `open_issues`: JSON blockers, questions, TODOs
- `recent_changes`: Summary of recent code modifications
- `last_cli` / `last_session_id`: Last CLI used and its session
- `context_snippet`: Last N relevant conversation turns (pre-compressed)
- `switch_count`: How many times CLIs have been switched for this workspace

**Lifecycle**: Created on first CLI session in a workspace -> Updated at session end -> Read at next session start -> Cleared when user marks task complete.

---

## V2 Complete Conversation Sync Engine

### Ingest Pipeline

```
Source (CLI/Browser) --> Ingest API --> Parser --> Dedup --> Store --> Index --> Compress --> Summarize
```

| Step | Description |
|------|-------------|
| Ingest API | `POST /api/v2/conversations` accepts raw conversation data |
| Parser | Normalizes platform-specific formats into `archive_messages` rows |
| Dedup | `content_hash` check prevents duplicate imports |
| Store | Writes to `archive_conversations` + `archive_messages` |
| Index | Upserts into ChromaDB vector store |
| Compress | Applies rule-based compression per message |
| Summarize | AI-generates summary (async, non-blocking) |

### Platform-Specific Importers

| Platform | Source | Capture Method |
|----------|--------|---------------|
| Claude Code | `~/.claude/projects/*/` | Session-end hook + file import |
| Codex CLI | `~/.codex/sessions/` | File import |
| Gemini CLI | `~/.gemini/tmp/` | File import |
| Antigravity | `~/.gemini/antigravity/conversations/` | Protobuf import |
| Browser-based | Browser extension | Manual sync button |

### Sync Strategies

1. **Polling sync**: Periodically scans CLI session directories for new/updated files (configurable interval, default 5 minutes)
2. **File watching**: Uses watchdog to detect file changes in real-time (optional, requires `watchdog` package)

Both strategies feed discovered sessions through the V2 ingest pipeline with fingerprint-based dedup.

---

## V2 CLI Quick Switch Mechanism

### Switch Flow

```
User: "Switch to Codex"
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
|    - Backup existing file     |
+-------------------------------+
```

### Context Budget Strategy

Token budget allocation varies per CLI based on their context window size:

| CLI | Working | Core | Archive | Total |
|-----|---------|------|---------|-------|
| Claude Code (~200K) | 1,000-3,000 | 2,000-5,000 | 5,000-20,000 | ~8,000-28,000 |
| Codex CLI (~128K) | 1,000-2,000 | 2,000-4,000 | 3,000-10,000 | ~6,000-16,000 |
| Gemini CLI (~1M) | 1,000-3,000 | 3,000-8,000 | 20,000-100,000 | ~24,000-111,000 |
| Antigravity (~128K) | 1,000-2,000 | 2,000-4,000 | 3,000-10,000 | ~6,000-16,000 |

### Context Assembly Algorithm

1. **Working memory** is always injected in full (highest priority)
2. **Core memories** are sorted by: pinned first, then priority DESC, then relevance to active task. Fills up to 40% of remaining budget.
3. **Archive excerpt** uses compressed messages from recent sessions, filling remaining budget
4. Final document is formatted per target CLI's context file format (CLAUDE.md, AGENTS.md, GEMINI.md)

---

## V2 Content Compression System

### Rule-Based Compression (~90% of content)

Applied at import time, stored in `archive_messages.compressed`:

| Content Type | Compression Rule |
|-------------|-----------------|
| Tool: Read | `[Read: {path}, {lines} lines]` |
| Tool: Bash | `[Bash: {cmd} -> {exit_code}]` |
| Tool: Edit | `[Edit {file}: {description}]` |
| Tool: Search/Grep | `[Search "{query}" -> {n} matches]` |
| Tool: Write | `[Write: {path}, {lines} lines]` |
| Long code blocks (>20 lines) | First 5 lines + `// ...{n} lines omitted` + last 3 lines |
| Error stacks (>10 lines) | First line + root cause + last line |
| Thinking blocks | `[Thinking: {summary}...]` |

### AI-Assisted Compression (~10%)

For messages that don't match rules but exceed 2000 tokens, AI summarization preserves decisions, action items, errors, and key technical details while removing verbose explanations and filler.

---

## V2 API Design

### Endpoint Summary

All V2 endpoints are under `/api/v2/` prefix. V1 endpoints remain unchanged for backward compatibility.

#### Archive (Conversations)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v2/conversations` | Ingest a full conversation with structured messages |
| `GET` | `/api/v2/conversations` | List conversations (paginated, filtered) |
| `GET` | `/api/v2/conversations/{id}` | Get conversation with messages |
| `GET` | `/api/v2/conversations/{id}/messages` | Get messages only (paginated) |
| `GET` | `/api/v2/conversations/{id}/compressed` | Get compressed message view |
| `DELETE` | `/api/v2/conversations/{id}` | Delete conversation and its messages |

#### Working Memory
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v2/working-memory/{workspace}` | Get working memory for a workspace |
| `PUT` | `/api/v2/working-memory/{workspace}` | Update working memory (upsert) |
| `DELETE` | `/api/v2/working-memory/{workspace}` | Clear working memory |
| `GET` | `/api/v2/working-memory` | List all active working memories |

#### Switch
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v2/switch` | Execute CLI switch with context injection |
| `GET` | `/api/v2/switch/preview` | Preview what would be injected (dry run) |
| `GET` | `/api/v2/switch/history` | List recent switches |

#### Sync
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v2/sync/status` | Get current sync status |
| `POST` | `/api/v2/sync/trigger` | Manually trigger incremental sync |

#### Import/Export
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v2/import/local` | Import local CLI sessions (V2 structured) |
| `POST` | `/api/v2/export/{client}` | Generate export for a specific CLI |
| `POST` | `/api/v2/migrate/v1-to-v2` | Migrate V1 data to V2 archive tables |

---

## V1 Architecture (Preserved)

The original V1 architecture operates as a three-layer pipeline that remains fully functional:

### 1. Data Collection Layer

**Components**:
- **Browser Extension** (`browser-extension/`): Chrome Extension Manifest V3, monitors Claude Web UI via DOM observation
- **Claude Code Hook** (`claude-code-integration/hooks/`): Bash scripts capturing session data via curl
- **Local Importers** (`backend/local_importer.py`): File-based import from codex, claude_code, gemini_cli, antigravity

### 2. Memory Hub Service (Central Intelligence)

**Components**:
- **Core Service** (`backend/main.py`): FastAPI REST API server with 40+ endpoints
- **Database Layer** (`backend/database.py`): SQLite for structured metadata (conversations, topics, decisions, preferences, relations)
- **ChromaDB** (`backend/vector_store.py`): Hash-based local embeddings for semantic search
- **AI Analyzer** (`backend/ai_analyzer.py`): Multi-provider summarization with fallback
- **Memory Consolidation** (`backend/memory_consolidation.py`): Forgetting curve, daily consolidation
- **Preference Learning** (`backend/preference_learning.py`): Pattern-based preference extraction

### 3. Context Injection Layer

**Components**:
- **Session Start Hook** (`claude-code-integration/hooks/session-start.sh`): Generates/updates `.claude/CLAUDE.md`
- **Client Exports** (`backend/client_exports.py`): Export profiles for claude_code, codex, gemini_cli

---

## Data Flow (V2)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. CAPTURE                                                  │
│                                                             │
│  User interacts with any CLI or browser AI                  │
│         ↓                                                   │
│  Sync engine detects new session (polling/watchdog)         │
│         ↓                                                   │
│  POST /api/v2/conversations (structured messages)           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. PROCESS (Memory Hub V2)                                  │
│                                                             │
│  Parse into archive_messages (normalize per platform)       │
│         ↓                                                   │
│  Dedup via content_hash                                     │
│         ↓                                                   │
│  Compress (rule-based + AI fallback)                        │
│         ↓                                                   │
│  Store in archive_conversations + archive_messages          │
│         ↓                                                   │
│  Update working_memory if working_state provided            │
│         ↓                                                   │
│  Vectorize and index in ChromaDB                            │
│         ↓                                                   │
│  Generate summary (AI or fallback)                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. SWITCH / INJECT                                          │
│                                                             │
│  User requests switch: POST /api/v2/switch                  │
│         ↓                                                   │
│  Context Assembly Engine:                                   │
│    - Working memory (full)                                  │
│    - Core memories (filtered by priority/relevance)         │
│    - Archive excerpt (compressed, budget-limited)           │
│         ↓                                                   │
│  Format for target CLI (CLAUDE.md / AGENTS.md / GEMINI.md) │
│         ↓                                                   │
│  Write context file + backup existing                       │
│         ↓                                                   │
│  Target CLI reads context file automatically                │
│         ↓                                                   │
│  Full context continuity — no re-briefing needed            │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

### 1. Local-First Architecture
- All data stored locally (SQLite + ChromaDB)
- No cloud dependencies, privacy-preserving
- Fast access (no network latency)

### 2. Three-Layer Memory (V2)
- Inspired by MemGPT (virtual context management) and Mem0 (extract-consolidate-retrieve)
- Archive = complete history, Core = distilled knowledge, Working = active task state
- Each layer serves a different purpose during context assembly

### 3. Token-Budgeted Context Assembly
- Each CLI has a per-layer token budget based on its context window
- Working memory always injected in full (highest priority)
- Core memories filtered by priority and relevance
- Archive fills remaining budget with compressed excerpts

### 4. Rule-Based Compression First
- Deterministic, fast, no API calls needed
- Covers ~90% of compressible content (tool calls, code blocks, error stacks)
- AI compression only for the remaining ~10%

### 5. Backward Compatibility
- V1 API endpoints continue to work unchanged
- V1 `full_content` can be reconstructed from `archive_messages` on-the-fly
- Migration preserves 100% of existing data

### 6. Modular Design
- Each V2 component is a separate module: `database_v2.py`, `message_compressor.py`, `context_assembler.py`, `switch_engine.py`, `sync_scheduler.py`
- Export adapters are independent of the assembly engine
- New CLIs can be added by defining a token budget and export profile

---

## Research Foundations

V2's design draws from recent research in memory systems and context engineering:

| Concept | Source | Application in V2 |
|---------|--------|-------------------|
| Virtual context management | MemGPT (2023) | Three-layer memory with context paging during CLI switch |
| Extract-consolidate-retrieve | Mem0 (2025) | Conversation processing pipeline |
| Zettelkasten-style atomic notes | A-MEM (NeurIPS 2025) | Core memories as linked, tagged, evolving knowledge units |
| Self-improving context curation | ACE (ICLR 2026) | Context assembly evolves based on what proved useful |
| Importance-based trimming | ACON (2025) | Token-budgeted context assembly with priority sorting |
| Structured > raw context | BEAM (2025) | Three-layer structure outperforms raw conversation dumping |

See [Full Research Survey](docs/research/2026-03-18-memory-context-engineering-survey.md) for details.

---

## Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Backend Service | FastAPI | Async support, fast, easy to deploy |
| Metadata Storage | SQLite (WAL mode) | Zero-config, local, concurrent reads |
| Vector Search | ChromaDB | Python-native, local-first |
| Browser Extension | Chrome Manifest V3 | Modern standard, secure |
| Hooks | Bash scripts + Python CLI | Simple, portable |
| Compression | Rule-based + AI fallback | Fast deterministic path with quality fallback |
| Sync | Polling + watchdog | Reliable with optional real-time detection |
| AI Providers | Claude, OpenAI, DeepSeek, Qwen, etc. | Multi-provider with fallback |

---

## Security & Privacy

- All data stored locally in `data/` directory
- Memory Hub only listens on localhost (127.0.0.1)
- No external network access required (AI providers optional)
- Content-hash dedup prevents accidental data leaks through duplicate storage
- Switch mechanism backs up existing context files before overwriting
- Full data export and deletion capability

---

## Performance Targets

- Conversation capture latency: < 100ms
- Context generation time: < 2s
- Vector search response: < 500ms
- CLI switch (context assembly + file write): < 3s
- Compression ratio for tool-heavy conversations: < 30% of original tokens
- Memory footprint: < 200MB
- Database size: ~10MB per 1000 conversations

---

## File Structure (V2)

```
backend/
    main.py              FastAPI app with V1 endpoints + V2 router mount
    database.py          V1 database layer
    database_v2.py       V2 database: archive tables, working memory, migration
    models.py            V1 Pydantic models
    models_v2.py         V2 Pydantic models: conversation, message, switch, import
    api_v2.py            V2 API endpoints (/api/v2/*)
    message_compressor.py Rule-based content compression engine
    compression.py       Compression compatibility layer + utilities
    context_assembler.py Three-layer context assembly with token budgeting
    switch_engine.py     CLI switch orchestration
    sync_scheduler.py    Polling + watchdog sync for conversation capture
    client_exports.py    Export profiles for claude_code, codex, gemini_cli
    vector_store.py      ChromaDB with local hash embeddings
    ai_analyzer.py       Multi-provider AI analysis with fallback
    local_importer.py    Platform-specific session importers
    memory_consolidation.py  Forgetting curve, daily consolidation
    preference_learning.py   Pattern-based preference extraction
    backup_export.py     Backup/restore with scheduling
```

---

**Document Version**: 2.0
**Last Updated**: 2026-03-18
**Status**: V2 Architecture — Implementation Complete
