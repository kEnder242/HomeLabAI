#!/bin/bash
MODE=${1:-SERVICE} # Default to SERVICE if no arg provided

cd ~/AcmeLab
# Kill old instances
pkill -f acme_lab.py || true
pkill -f pinky_node.py || true
pkill -f archive_node.py || true
pkill -f brain_node.py || true

echo "Starting Acme Lab in $MODE mode..."
# Start new instance detached
nohup ./.venv/bin/python -u src/acme_lab.py --mode "$MODE" > server.log 2>&1 < /dev/null &
PID=$!
echo "Acme Lab PID: $PID"

# Follow logs until the server process exits
tail --pid=$PID -f server.log
