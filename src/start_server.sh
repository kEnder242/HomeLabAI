#!/bin/bash
cd ~/VoiceGateway
# Kill old instance
pkill -f audio_server.py || true
# Start new instance detached
nohup ./.venv/bin/python src/audio_server.py > server.log 2>&1 < /dev/null &
echo "Server started with PID $!"
