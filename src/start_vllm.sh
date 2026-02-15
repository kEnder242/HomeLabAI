#!/bin/bash
VENV_PATH="/home/jallred/Dev_Lab/HomeLabAI/.venv"
SERVER_SCRIPT="/home/jallred/Dev_Lab/HomeLabAI/src/vllm_liger_server.py"
LOG_FILE="/home/jallred/Dev_Lab/HomeLabAI/vllm_server.log"
PID_FILE="/home/jallred/Dev_Lab/HomeLabAI/server_vllm.pid"

MODEL_PATH="${1:-/usr/share/ollama/.ollama/models/blobs/sha256-7462734796d67c40ecec2ca98eddf970e171dbb6b370e43fd633ee75b69abe1b}"

echo "--- vLLM Alpha Startup: $MODEL_PATH ---"

# Explicitly disable V1 and use transformers backend for Liger compatibility
export VLLM_USE_V1=0

# Start the vLLM server in the background
# Using --load-format gguf for native Ollama blob support
# Pointing --tokenizer to the weights file to read metadata directly
nohup $VENV_PATH/bin/python3 $SERVER_SCRIPT \
    --model "$MODEL_PATH" \
    --load-format "gguf" \
    --tokenizer "$MODEL_PATH" \
    --host "0.0.0.0" \
    --port 8088 \
    --gpu-memory-utilization 0.4 \
    --max-model-len 4096 \
    --enforce-eager \
    --enable-lora \
    --max-loras 4 \
    > $LOG_FILE 2>&1 &

echo $! > $PID_FILE
echo "Server launched with PID: $(cat $PID_FILE)"
