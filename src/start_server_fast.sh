#!/bin/bash
MODE=${1:-MOCK_BRAIN}
HOST_DNS="z87-Linux.local"

# 1. Resolve IP once to avoid mDNS thrashing in loops
echo "🔍 Resolving $HOST_DNS..."
HOST_IP=$(ping -c 1 $HOST_DNS | head -n 1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+')

if [ -z "$HOST_IP" ]; then
    echo "❌ Failed to resolve $HOST_DNS. Is the host online?"
    exit 1
fi
echo "✅ Resolved to: $HOST_IP"
TARGET="jallred@$HOST_IP"

echo "🚀 Starting Acme Lab (Fast Mode) in Tmux..."
# Kill old session
ssh -i ~/.ssh/id_rsa_wsl "$TARGET" "tmux kill-session -t acme_fast 2>/dev/null || true"

# Start new session
ssh -i ~/.ssh/id_rsa_wsl "$TARGET" "tmux new-session -d -s acme_fast 'cd ~/AcmeLab && DISABLE_EAR=1 ./.venv/bin/python3 src/acme_lab.py --mode $MODE'"

# Verify
sleep 2
ssh -i ~/.ssh/id_rsa_wsl "$TARGET" "tmux capture-pane -pt acme_fast"