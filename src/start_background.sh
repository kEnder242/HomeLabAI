#!/bin/bash
# src/start_background.sh
MODE=$1

# Cleanup previous instances
pkill -f acme_lab.py

cd ~/AcmeLab
source .venv/bin/activate
nohup python src/acme_lab.py --mode $MODE > server.log 2>&1 &
echo $! > server.pid
echo "Server started with PID $(cat server.pid)"
sleep 1 # Wait a beat to ensure PID file is flushed
