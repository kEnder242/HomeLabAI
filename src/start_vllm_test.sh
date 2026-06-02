#!/bin/bash
MODEL_PATH=$1
LAB_VENV_PYTHON=$2

$LAB_VENV_PYTHON -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --host 0.0.0.0 \
    --port 8088 \
    --served-model-name unified-base \
    --gpu-memory-utilization 0.4 \
    --max-model-len 8192 \
    --enforce-eager \
    --attention-backend TRITON_ATTN \
    --enable-prefix-caching \
    > vllm_server.log 2>&1 &

PID=$!
echo $PID > run/vllm.pid
echo "Sovereign Node (TEST) launched with PID: $PID"
