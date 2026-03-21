#!/bin/bash

# Claude Code Session Start Hook
# Automatically injects relevant context from Memory Hub into CLAUDE.md

# Get current working directory
WORKING_DIR="${CLAUDE_WORKING_DIR:-$(pwd)}"

# Check if Memory Hub is running
if ! curl -s http://localhost:8765/health > /dev/null 2>&1; then
    echo "⚠️  Memory Hub not running. Skipping context injection."
    exit 0
fi

# Request context from Memory Hub
CONTEXT=$(curl -s "http://localhost:8765/api/context?working_dir=$WORKING_DIR&hours=24" | jq -r '.context')

if [ -z "$CONTEXT" ] || [ "$CONTEXT" = "null" ]; then
    echo "ℹ️  No recent context found."
    exit 0
fi

# Prepare CLAUDE.md path
CLAUDE_DIR="$WORKING_DIR/.claude"
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"

# Create .claude directory if it doesn't exist
mkdir -p "$CLAUDE_DIR"

# Backup existing CLAUDE.md
if [ -f "$CLAUDE_MD" ]; then
    cp "$CLAUDE_MD" "$CLAUDE_MD.backup"
    ORIGINAL_CONTENT=$(cat "$CLAUDE_MD.backup")
else
    ORIGINAL_CONTENT=""
fi

# Write new CLAUDE.md with injected context
cat > "$CLAUDE_MD" << EOF
$CONTEXT

---

# Original Memory

$ORIGINAL_CONTENT
EOF

echo "✅ Context injected to CLAUDE.md"
