#!/bin/bash

# Codex CLI Post-Session Hook
# Imports the session and updates working memory after Codex ends.

WORKING_DIR="${CODEX_WORKING_DIR:-$(pwd)}"
MEMORY_HUB_URL="${MEMORY_HUB_URL:-http://localhost:8765}"

# Check if Memory Hub is running
if ! curl -s "$MEMORY_HUB_URL/health" > /dev/null 2>&1; then
    exit 0
fi

# Update working memory
curl -s -X PUT "$MEMORY_HUB_URL/api/v2/working-memory/$(python3 -c "import urllib.parse; print(urllib.parse.quote('$WORKING_DIR', safe=''))")" \
  -H "Content-Type: application/json" \
  -d "{\"workspace_path\": \"$WORKING_DIR\", \"last_cli\": \"codex\"}" \
  > /dev/null 2>&1

# Import latest Codex session
curl -s -X POST "$MEMORY_HUB_URL/api/v2/import/local" \
  -H "Content-Type: application/json" \
  -d '{"source": "codex", "limit": 1}' \
  > /dev/null 2>&1
