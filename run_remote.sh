#!/bin/bash
MODE=${1:-HOSTING}

# 1. Sync
echo "🚀 [1/3] Syncing code to jallred@z87-Linux.local..."
./sync_to_linux.sh

# 2. Run Remote (Nohup/Tail)
echo "🔋 [2/3] Starting Acme Lab in $MODE mode..."
ssh -t -i ~/.ssh/id_rsa_wsl jallred@z87-Linux.local "bash ~/AcmeLab/src/start_server.sh $MODE"
