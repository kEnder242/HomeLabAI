#!/bin/bash
# Local Blocking Integration Driver
# Usage: ./src/copilot.sh [MODE]
# Default Mode: DEBUG_BRAIN

MODE=${1:-DEBUG_BRAIN}
PROJECT_ROOT="/home/jallred/Dev_Lab/HomeLabAI"

echo "🚀 Starting LOCAL Integration Server (Mode: $MODE)..."
echo "⏳ Timeout: 300s (Agent Safety Cap)"
echo "💡 Instructions: Run Client (v2.2.0) -> Test -> Ctrl+C to finish."

# 1. Load MPS Environment (if present)
if [ -f "$PROJECT_ROOT/mps_env.sh" ]; then
    source "$PROJECT_ROOT/mps_env.sh"
    echo "✅ MPS Enabled."
fi

# 2. Run Locally (No SSH needed)
# Using 'timeout' to ensure Agent return
cd "$PROJECT_ROOT" && timeout 290s ./.venv/bin/python3 -u src/acme_lab.py --mode $MODE --afk-timeout 60

EXIT_CODE=$?
echo "🛑 Server Returned (Exit Code: $EXIT_CODE)."