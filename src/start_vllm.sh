#!/bin/bash
VENV_PATH="/home/jallred/Dev_Lab/HomeLabAI/.venv"
SERVER_SCRIPT="/home/jallred/Dev_Lab/HomeLabAI/src/vllm_liger_server.py"
LOG_FILE="/home/jallred/Dev_Lab/HomeLabAI/vllm_server.log"
PID_FILE="/home/jallred/Dev_Lab/HomeLabAI/server_vllm.pid"

MODEL_PATH="/home/jallred/AcmeLab/models/mistral-7b-awq"

echo "--- vLLM Alpha Startup: Mistral-7B-AWQ ---"

# Start the vLLM server in the background
nohup $VENV_PATH/bin/python3 $SERVER_SCRIPT \
    --model "$MODEL_PATH" \
    --quantization "awq" \
    --host "0.0.0.0" \
    --port 8088 \
    --gpu-memory-utilization 0.4 \
    --max-model-len 2048 \
    --enforce-eager \
    > $LOG_FILE 2>&1 &

echo $! > $PID_FILE
echo "Server launched with PID: $(cat $PID_FILE)"
