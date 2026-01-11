#!/bin/bash
MODE=${1:-MOCK_BRAIN}

echo "🚀 Starting Acme Lab (Fast Mode) in Tmux..."
# Kill old session
ssh -i ~/.ssh/id_rsa_wsl jallred@192.168.1.221 "tmux kill-session -t acme_fast 2>/dev/null || true"

# Start new session
ssh -i ~/.ssh/id_rsa_wsl jallred@192.168.1.221 "tmux new-session -d -s acme_fast 'cd ~/AcmeLab && DISABLE_EAR=1 ./.venv/bin/python3 src/acme_lab.py --mode $MODE'"

# Verify
sleep 2
ssh -i ~/.ssh/id_rsa_wsl jallred@192.168.1.221 "tmux capture-pane -pt acme_fast"
