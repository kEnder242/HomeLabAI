#!/bin/bash
# --- vLLM Unified Base Startup (Llama-3.2-3B-AWQ) ---
MODEL_PATH=$1
LAB_VENV_PYTHON="/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3"

if [ -z "$MODEL_PATH" ]; then
    MODEL_PATH="/home/jallred/.cache/huggingface/hub/models--casperhansen--llama-3.2-3b-instruct-awq/snapshots/272b3bde867b606760447deb9a4d2719fbdfd3ae"
fi

echo "--- vLLM Alpha Startup: $MODEL_PATH ---"

# Critical: Remove VLLM_USE_V1=0 as it's causing deadlocks on Turing.
# Defaulting to standard v0 backend.

$LAB_VENV_PYTHON -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --load-format auto \
    --host 0.0.0.0 \
    --port 8088 \
    --gpu-memory-utilization 0.5 \
    --served-model-name unified-base \
    --max-model-len 8192 \
    --enforce-eager \
    --trust-remote-code \
    --enable-auto-tool-choice \
    --tool-call-parser llama3_json \
    > HomeLabAI/vllm_server.log 2>&1 &

echo "Server launched with PID: $!"
