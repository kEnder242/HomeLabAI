#!/bin/bash
MODE=${1:-MOCK_BRAIN}

echo "🚀 Starting Acme Lab (Fast Mode) in Tmux..."
# Kill old session
ssh -i ~/.ssh/id_rsa_wsl jallred@z87-Linux.local "tmux kill-session -t acme_fast 2>/dev/null || true"

# Start new session
ssh -i ~/.ssh/id_rsa_wsl jallred@z87-Linux.local "tmux new-session -d -s acme_fast 'cd ~/AcmeLab && DISABLE_EAR=1 ./.venv/bin/python3 src/acme_lab.py --mode $MODE'"

# Verify
sleep 2
ssh -i ~/.ssh/id_rsa_wsl jallred@z87-Linux.local "tmux capture-pane -pt acme_fast"
