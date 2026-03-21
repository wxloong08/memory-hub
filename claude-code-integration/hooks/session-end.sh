#!/bin/bash

# Claude Code Session End Hook
# Captures working state and saves to Memory Hub on session end.

WORKING_DIR="${CLAUDE_WORKING_DIR:-$(pwd)}"
MEMORY_HUB_URL="${MEMORY_HUB_URL:-http://localhost:8765}"

# Check if Memory Hub is running
if ! curl -s "$MEMORY_HUB_URL/health" > /dev/null 2>&1; then
    exit 0
fi

# Update working memory with last CLI info
curl -s -X PUT "$MEMORY_HUB_URL/api/v2/working-memory/$(python3 -c "import urllib.parse; print(urllib.parse.quote('$WORKING_DIR', safe=''))")" \
  -H "Content-Type: application/json" \
  -d "{\"workspace_path\": \"$WORKING_DIR\", \"last_cli\": \"claude_code\"}" \
  > /dev/null 2>&1

# Import latest Claude Code session
curl -s -X POST "$MEMORY_HUB_URL/api/v2/import/local" \
  -H "Content-Type: application/json" \
  -d '{"source": "claude_code", "limit": 1}' \
  > /dev/null 2>&1
