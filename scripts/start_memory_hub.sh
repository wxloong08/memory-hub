#!/bin/bash

# Start Memory Hub Service
# Usage: ./scripts/start_memory_hub.sh

set -e

echo "🚀 Starting Claude Memory Hub..."

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to backend directory
cd "$PROJECT_ROOT/backend"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate || source venv/Scripts/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# Create data directory
mkdir -p "$PROJECT_ROOT/data"

# Start server
echo "✅ Memory Hub starting on http://localhost:8765"
echo ""
uvicorn main:app --reload --port 8765
