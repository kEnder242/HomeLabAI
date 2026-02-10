#!/bin/bash

# Configuration
VENV_PATH="/home/jallred/Dev_Lab/HomeLabAI/.venv"
SERVER_SCRIPT="/home/jallred/Dev_Lab/HomeLabAI/src/vllm_liger_server.py"
LOG_FILE="/home/jallred/.gemini/tmp/6c16f13d46c3be1dbe69b7b7b11534d5109576b3a3ee22b0278ab7c0d1abf907/vllm_server.log"
PID_FILE="/home/jallred/Dev_Lab/HomeLabAI/server_vllm.pid"

echo "--- vLLM + Liger Pilot Startup ---"

# 1. Stop local Ollama (if running)
echo "Stopping local Ollama service to free VRAM..."
pkill ollama 2>/dev/null || echo "Ollama not running."

# 2. Start the vLLM server in the background
echo "Launching vLLM-Liger server..."
nohup $VENV_PATH/bin/python3 $SERVER_SCRIPT \
    --model "TheBloke/Mistral-7B-Instruct-v0.2-AWQ" \
    --quantization "awq" \
    --host "0.0.0.0" \
    --port 8088 \
    --gpu-memory-utilization 0.6 \
    --max-model-len 4096 \
    > $LOG_FILE 2>&1 &

SERVER_PID=$!
echo $SERVER_PID > $PID_FILE

echo "Server launched with PID: $SERVER_PID"
echo "Logs available at: $LOG_FILE"
echo "Waiting for readiness (this may take several minutes as model downloads/loads)..."