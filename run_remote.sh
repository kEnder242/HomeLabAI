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

# Start server in background using the helper script
echo "🔋 [2/3] Starting Acme Lab in $MODE mode (Background)..."

ssh -i ~/.ssh/id_rsa_wsl $REMOTE_HOST "bash ~/AcmeLab/src/start_background.sh $MODE"

echo "📜 [3/3] Tailing logs (Ctrl+C to stop)..."
# We tail the log locally. We use a loop to check if the process is still alive.
# If the process dies (e.g. version mismatch), we stop tailing and exit.

ssh -i ~/.ssh/id_rsa_wsl $REMOTE_HOST "tail -f --pid=\$(cat $REMOTE_DIR/server.pid) $REMOTE_DIR/server.log"

echo "🛑 Server process exited."
