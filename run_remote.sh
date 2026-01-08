#!/bin/bash
# run_remote.sh
# Usage: ./run_remote.sh [SERVICE|DEBUG_PINKY|DEBUG_BRAIN]
# Automates the Sync -> Deploy -> Run -> Log Watch loop.

MODE=${1:-DEBUG_PINKY}
REMOTE_HOST="jallred@z87-Linux.local"
REMOTE_DIR="~/AcmeLab"

echo "🚀 [1/3] Syncing code to $REMOTE_HOST..."
./sync_to_linux.sh > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ Sync failed."
    exit 1
fi

echo "🔋 [2/3] Starting Acme Lab in $MODE mode..."
# We use a trap to kill the remote server when this script is Ctrl+C'd
trap "echo '🛑 Stopping remote server...'; ssh -i ~/.ssh/id_rsa_wsl $REMOTE_HOST 'pkill -f acme_lab.py'; exit" INT TERM

# Start server and immediately tail logs
# We use -t to allocate a TTY for color output if possible, but mainly to keep the session alive
ssh -t -i ~/.ssh/id_rsa_wsl $REMOTE_HOST "
    cd $REMOTE_DIR && \
    chmod +x src/start_server.sh && \
    ./src/start_server.sh $MODE
"
