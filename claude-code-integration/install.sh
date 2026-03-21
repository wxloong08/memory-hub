#!/bin/bash

set -e

echo "🔧 Installing Claude Code Memory Integration..."

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
HOOKS_DIR="$HOME/.claude/hooks"

# Create hooks directory if it doesn't exist
mkdir -p "$HOOKS_DIR"

# Copy session-start hook
cp "$SCRIPT_DIR/hooks/session-start.sh" "$HOOKS_DIR/session-start.sh"
chmod +x "$HOOKS_DIR/session-start.sh"

echo "✅ Hook installed to $HOOKS_DIR/session-start.sh"
echo ""
echo "📝 Next steps:"
echo "1. Start Memory Hub: cd backend && uvicorn main:app --port 8765"
echo "2. Open Claude Code in any project"
echo "3. Context will be automatically injected!"
