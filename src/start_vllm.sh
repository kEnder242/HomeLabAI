#!/bin/bash
VENV_PATH="/home/jallred/Dev_Lab/HomeLabAI/.venv"
SERVER_SCRIPT="/home/jallred/Dev_Lab/HomeLabAI/src/vllm_liger_server.py"
LOG_FILE="/home/jallred/Dev_Lab/HomeLabAI/vllm_server.log"
PID_FILE="/home/jallred/Dev_Lab/HomeLabAI/server_vllm.pid"

MODEL_PATH="${1:-/home/jallred/.cache/huggingface/hub/models--casperhansen--llama-3.2-3b-instruct-awq/snapshots/272b3bde867b606760447deb9a4d2719fbdfd3ae}"

echo "--- vLLM Alpha Startup: $MODEL_PATH ---"

# Explicitly disable V1 and use transformers backend for Liger compatibility
export VLLM_USE_V1=0

# Start the vLLM server in the background
# Using --load-format auto for safetensors support
nohup $VENV_PATH/bin/python3 $SERVER_SCRIPT \
    --model "$MODEL_PATH" \
    --load-format "auto" \
    --host "0.0.0.0" \
    --port 8088 \
    --gpu-memory-utilization 0.4 --served-model-name unified-base \
    --max-model-len 4096 \
    --enforce-eager \
    --enable-lora \
    --max-loras 4 \
    > $LOG_FILE 2>&1 &

echo $! > $PID_FILE
echo "Server launched with PID: $(cat $PID_FILE)"
