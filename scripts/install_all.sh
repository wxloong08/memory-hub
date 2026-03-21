#!/bin/bash

# Complete Installation Script for Claude Memory System
# Usage: ./scripts/install_all.sh

set -e

echo "🔧 Installing Claude Cross-Platform Memory System"
echo "=================================================="
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Step 1: Install backend dependencies
echo "📦 Step 1/3: Installing backend dependencies..."
cd "$PROJECT_ROOT/backend"

if [ ! -d "venv" ]; then
    python -m venv venv
fi

source venv/bin/activate || source venv/Scripts/activate
pip install -q -r requirements.txt

echo "✅ Backend dependencies installed"
echo ""

# Step 2: Install Claude Code hook
echo "🪝 Step 2/3: Installing Claude Code hook..."
cd "$PROJECT_ROOT/claude-code-integration"

if [ -f "install.sh" ]; then
    bash install.sh
else
    echo "⚠️  Hook installation script not found (will be created in Task 4)"
fi

echo ""

# Step 3: Browser extension instructions
echo "🌐 Step 3/3: Browser Extension Installation"
echo "-------------------------------------------"
echo "Manual steps required:"
echo "1. Open Chrome and go to chrome://extensions/"
echo "2. Enable 'Developer mode' (toggle in top-right)"
echo "3. Click 'Load unpacked'"
echo "4. Select: $PROJECT_ROOT/browser-extension/"
echo ""

# Create data directory
mkdir -p "$PROJECT_ROOT/data"

echo "=================================================="
echo "✅ Installation Complete!"
echo ""
echo "Next steps:"
echo "1. Start Memory Hub: cd backend && uvicorn main:app --port 8765"
echo "2. Install browser extension (see instructions above)"
echo "3. Open Claude Code in any project"
echo ""
echo "For help, see README.md"
