#!/bin/bash

# Antigravity Context Injection Script
# Injects context from Memory Hub for Antigravity sessions.

WORKING_DIR="${ANTIGRAVITY_WORKING_DIR:-$(pwd)}"
MEMORY_HUB_URL="${MEMORY_HUB_URL:-http://localhost:8765}"

# Check if Memory Hub is running
if ! curl -s "$MEMORY_HUB_URL/health" > /dev/null 2>&1; then
    echo "Memory Hub not running. Skipping context injection."
    exit 0
fi

# Execute switch to inject context
RESULT=$(curl -s -X POST "$MEMORY_HUB_URL/api/v2/switch" \
  -H "Content-Type: application/json" \
  -d "{\"to_cli\": \"antigravity\", \"workspace_path\": \"$WORKING_DIR\"}")

STATUS=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)

if [ "$STATUS" = "ok" ]; then
    TOKENS=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('context_assembled',{}).get('total_tokens',0))" 2>/dev/null)
    echo "Context injected for Antigravity ($TOKENS tokens)"
else
    echo "Context injection skipped."
fi
