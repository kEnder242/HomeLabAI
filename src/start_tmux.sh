#!/bin/bash
MODE=${1:-HOSTING} # Default to HOSTING if no arg provided
SESSION="acmelab"

cd ~/AcmeLab

# Cleanup previous instances
echo "🧹 Cleaning up old processes..."
pkill -f acme_lab.py || true
pkill -f pinky_node.py || true
pkill -f archive_node.py || true
pkill -f brain_node.py || true
tmux kill-session -t $SESSION 2>/dev/null || true

echo "🚀 Starting Acme Lab in Tmux Session: '$SESSION' (Mode: $MODE)..."

# Start new session detached
# We use a pipe to log output to file AND keep it in the buffer
tmux new-session -d -s $SESSION "bash -c './.venv/bin/python -u src/acme_lab.py --mode $MODE 2>&1 | tee server.log'"

# Wait for PID (Scanning the log is safer than $! with tmux)
echo "⏳ Waiting for Lab to initialize..."
timeout 60s bash -c 'until grep -q "Lab Doors Open" server.log; do sleep 0.5; done'

if grep -q "Lab Doors Open" server.log; then
    echo "✅ Lab is UP."
    # Find the PID of the python process
    PID=$(pgrep -f "src/acme_lab.py")
    echo "🔬 Tracking PID: $PID"
    # Tail the log until the process dies
    tail --pid=$PID -f server.log
else
    echo "❌ Lab failed to start. Checking log:"
    cat server.log
    exit 1
fi
