#!/bin/bash
MODE=${1:-HOSTING}

# 1. Sync
echo "🚀 [1/3] Syncing code to jallred@z87-Linux.local..."
./sync_to_linux.sh

# 2. Run Remote (Nohup/Tail)
echo "🔋 [2/3] Starting Acme Lab in $MODE mode..."
# Use nohup to keep it running after disconnect
# We use a trick to get the PID: print it inside the shell
ssh -i ~/.ssh/id_rsa_wsl jallred@z87-Linux.local "cd ~/AcmeLab && (pkill -f acme_lab.py || true) && DISABLE_EAR=$DISABLE_EAR nohup ./.venv/bin/python3 -u src/acme_lab.py --mode $MODE > server_boot.log 2>&1 & echo \"Acme Lab PID: \$!\""
