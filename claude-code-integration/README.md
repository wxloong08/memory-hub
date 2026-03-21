# Claude Code Hook Integration

This directory contains the Claude Code hook integration for the Memory System.

## Files

- `hooks/session-start.sh` - Hook that runs when Claude Code starts a session
- `install.sh` - Installation script to copy the hook to Claude Code's hooks directory

## Installation

Run the installation script:

```bash
cd claude-code-integration
./install.sh
```

This will copy the session-start hook to `~/.claude/hooks/session-start.sh`.

## How It Works

1. When Claude Code starts a session, it automatically runs `session-start.sh`
2. The hook checks if Memory Hub is running on `localhost:8765`
3. If running, it requests recent context for the current working directory
4. Context is injected into `.claude/CLAUDE.md` in the project
5. Claude Code reads this file and has access to recent conversation history

## Requirements

- Memory Hub service must be running on port 8765
- `curl` and `jq` must be installed on the system

## Error Handling

- If Memory Hub is not running, the hook exits gracefully with a warning
- If no recent context is found, the hook exits without modifying CLAUDE.md
- Existing CLAUDE.md content is preserved and appended after the injected context
