# Claude Cross-Platform Memory System

Automatically capture and sync conversations across Claude platforms (Web, Code, Antigravity) to provide seamless context continuity.

## Overview

This system eliminates the need to repeat context when switching between Claude platforms. When you discuss a project in Claude Web and later open Claude Code, it automatically knows what you talked about.

## Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Start Memory Hub

```bash
cd backend
uvicorn main:app --reload --port 8765
```

The Memory Hub will start on `http://localhost:8765`

### 3. Install Claude Code Hook

```bash
cd claude-code-integration
./install.sh
```

This installs the session-start hook that automatically injects context.

### 4. Install Browser Extension

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top-right)
3. Click "Load unpacked"
4. Select the `browser-extension/` folder

## How It Works

### Automatic Context Flow

1. **Capture**: Browser extension monitors Claude Web conversations
2. **Process**: Memory Hub stores and analyzes conversations
3. **Inject**: Claude Code hook automatically loads relevant context on startup

### Example Workflow

**Morning (Claude Web)**:
```
You: "I want to build a POD multi-agent system"
Claude: "Great! Let's design the architecture..."
[Browser extension captures this conversation]
```

**Afternoon (Claude Code)**:
```bash
cd my-project
claude
```

Claude Code automatically sees:
```markdown
# Auto-Generated Context

## Recent Activity

### claude_web - 2025-03-09 10:30
**Summary**: Build a POD multi-agent system
**Importance**: 9/10

You discussed building a POD multi-agent system with 8 agents...
```

Claude continues the conversation without you repeating anything.

## Architecture

```
Browser Extension → Memory Hub (FastAPI) → SQLite + ChromaDB
                         ↓
Claude Code Hook ← Context Generator
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design.

## Project Structure

```
claude-memory-system/
├── backend/                      # Memory Hub service
│   ├── main.py                  # FastAPI server
│   ├── database.py              # SQLite operations
│   ├── models.py                # Data models
│   ├── context_generator.py     # Context generation
│   └── requirements.txt
│
├── browser-extension/           # Chrome extension
│   ├── manifest.json
│   ├── content_script.js        # Conversation capture
│   ├── background.js
│   └── popup.html
│
├── claude-code-integration/     # Claude Code hooks
│   ├── hooks/
│   │   └── session-start.sh    # Auto-inject context
│   └── install.sh
│
├── data/                        # Local storage
│   ├── memory.db               # SQLite database
│   └── conversations/          # Backup files
│
├── tests/                       # Test suite
└── docs/                        # Documentation
```

## API Endpoints

### Add Conversation
```bash
POST http://localhost:8765/api/conversations
{
  "platform": "claude_web",
  "timestamp": "2025-03-09T10:30:00Z",
  "messages": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi!"}
  ]
}
```

### Get Context
```bash
GET http://localhost:8765/api/context?hours=24&working_dir=/path/to/project
```

### Health Check
```bash
GET http://localhost:8765/health
```

## Development

### Run Tests

```bash
pytest tests/ -v
```

### Manual Testing

Test the API:
```bash
# Check health
curl http://localhost:8765/health

# Get context
curl "http://localhost:8765/api/context?hours=24"
```

## Configuration

### Memory Hub Settings

Edit `backend/config.py` (future):
- Port: Default 8765
- Database path: `data/memory.db`
- Importance threshold: 7 (only inject conversations rated 7+)
- Time window: 24 hours

### Hook Settings

Edit `~/.claude/hooks/session-start.sh`:
- Adjust time window: `hours=24`
- Change importance threshold: `min_importance=7`

## Troubleshooting

### Memory Hub Not Running
```bash
# Check if service is running
curl http://localhost:8765/health

# Start manually
cd backend
uvicorn main:app --port 8765
```

### Hook Not Working
```bash
# Check hook is installed
ls -la ~/.claude/hooks/session-start.sh

# Test hook manually
bash ~/.claude/hooks/session-start.sh
```

### Extension Not Capturing
1. Check extension is loaded in `chrome://extensions/`
2. Open browser console on Claude.ai
3. Look for "Claude Memory Collector" logs

## Privacy & Security

- **Local-first**: All data stored locally, never uploaded
- **Localhost-only**: Memory Hub only accessible from your machine
- **User control**: Delete any conversation anytime
- **No tracking**: No analytics or external connections

## Roadmap

### Phase 1: MVP (Current)
- ✅ Basic conversation capture
- ✅ SQLite storage
- ✅ Context injection
- ✅ Browser extension
- ✅ Claude Code hook

### Phase 2: Intelligence (Weeks 3-4)
- [ ] ChromaDB vector search
- [ ] Automatic conversation linking
- [ ] Improved importance scoring

### Phase 3: Advanced Memory (Weeks 5-6)
- [ ] Daily memory consolidation
- [ ] Memory decay (forgetting curve)
- [ ] Preference learning

### Phase 4: Extended Integration (Week 7)
- [ ] Antigravity support
- [ ] Web UI for memory management
- [ ] MCP server integration

## V2: Cross-CLI Context Switching

Memory Hub V2 adds a **three-layer memory architecture** and **CLI quick switch** -- enabling seamless context transfer between Claude Code, Codex CLI, Gemini CLI, and Antigravity.

### V2 Quick Start

```bash
# 1. Start the backend (same as V1)
cd backend
uvicorn main:app --reload --port 8765

# 2. Import existing CLI sessions into V2 archive
python cli/memory_hub.py import --source all

# 3. Save your current task state
python cli/memory_hub.py save-state --task "My current task"

# 4. Switch to another CLI with full context
python cli/memory_hub.py switch --to gemini_cli
```

### V2 Three-Layer Memory

| Layer | Purpose | Persistence |
|-------|---------|-------------|
| **Archive** | Full conversation transcripts with per-message compression | Permanent |
| **Core** | Structured knowledge: facts, preferences, decisions | Long-term |
| **Working** | Active task state per workspace | Session-scoped |

### V2 CLI Tool: memory-hub

```bash
memory-hub switch --to <cli>     # Switch CLI with context injection
memory-hub status                # View current workspace state
memory-hub save-state --task ... # Save working state manually
memory-hub import --source all   # Import local CLI sessions
memory-hub search <query>        # Search conversations
memory-hub history               # View switch history
```

See [CLI Switch Guide](docs/CLI_SWITCH_GUIDE.md) for full usage documentation.

### V2 Documentation

- [CLI Switch Guide](docs/CLI_SWITCH_GUIDE.md) -- User guide for CLI switching (Chinese)
- [API V2 Reference](docs/API_V2_REFERENCE.md) -- Complete V2 API documentation
- [Architecture](ARCHITECTURE.md) -- System design with V2 three-layer model
- [V2 Migration Guide](docs/V2_MIGRATION_GUIDE.md) -- Migrating from V1 to V2

---

## Contributing

This is an internal project. Team members:
- **Alex Chen**: Lead Architect
- **Sarah Kim**: Backend Development
- **Marcus Rodriguez**: Integration & Deployment
- **Emily Watson**: Browser Extension
- **David Park**: QA & Testing

## License

MIT License - Internal Use

## Support

For issues or questions, contact the team lead or check:
- Implementation Plan: `docs/plans/2025-03-09-cross-platform-memory-implementation.md`
- Design Document: `docs/plans/2025-03-09-cross-platform-memory-system-design.md`
- Architecture: `ARCHITECTURE.md`
