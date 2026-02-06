#!/bin/bash
# Blocking Integration Driver
# Usage: ./src/run_integration.sh [MODE]
# Default Mode: DEBUG_BRAIN

MODE=${1:-DEBUG_BRAIN}
HOST_DNS="z87-Linux.local"

# 1. Resolve IP
echo "🔍 Resolving $HOST_DNS..."
HOST_IP=$(ping -c 1 $HOST_DNS | head -n 1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+')
if [ -z "$HOST_IP" ]; then
    echo "❌ Failed to resolve $HOST_DNS."
    exit 1
fi

TARGET="jallred@$HOST_IP"

echo "🚀 Starting Blocking Integration Server (Mode: $MODE)..."
echo "⏳ Timeout: 300s (Agent Safety Cap)"
echo "💡 Instructions: Run Client -> Test -> Ctrl+C to finish."

# 2. Run Synchronously
# We removed the explicit -i key path to rely on ambient SSH agent/config
ssh -t "$TARGET" "cd ~/AcmeLab && timeout 290s ./.venv/bin/python3 -u src/acme_lab.py --mode $MODE --afk-timeout 60"

EXIT_CODE=$?
echo "🛑 Server Returned (Exit Code: $EXIT_CODE)."
