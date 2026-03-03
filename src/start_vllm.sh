#!/bin/bash
# --- vLLM Sovereign Base Startup (Qwen-2.5-3B-Instruct) ---
# [FEAT-145] Unified Sovereign Environment
MODEL_PATH=$1
LAB_VENV_PYTHON=$2

if [ -z "$LAB_VENV_PYTHON" ]; then
    LAB_VENV_PYTHON="/home/jallred/Dev_Lab/.venv_vllm_016/bin/python3"
fi

if [ -z "$MODEL_PATH" ]; then
    MODEL_PATH="/speedy/models/Qwen2.5-3B-Instruct"
fi

# [TURING BREAKTHROUGH] Force XFORMERS and P2P Disable for RTX 2080 Ti stability
export VLLM_ATTENTION_BACKEND=XFORMERS
export NCCL_P2P_DISABLE=1
export VLLM_USE_V1=0 # vLLM V1 still has issues on Turing; stick to V0 with XFORMERS

echo "--- vLLM Sovereign Ignition: $MODEL_PATH ---"
echo "Env: XFORMERS=1, NCCL_P2P_DISABLE=1, V1=0"

# [FEAT-030] Unity Pattern: Consume VLLM_EXTRA_ARGS from lab_attendant
# Path Hardening: We assume we are running from HomeLabAI/ or its parent.
$LAB_VENV_PYTHON -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --load-format auto \
    --host 0.0.0.0 \
    --port 8088 \
    --gpu-memory-utilization 0.6 \
    --served-model-name unified-base \
    --max-model-len 8192 \
    --enforce-eager \
    --trust-remote-code \
    --enable-auto-tool-choice \
    --tool-call-parser llama3_json \
    $VLLM_EXTRA_ARGS \
    > vllm_server.log 2>&1 &

echo "Sovereign Node launched with PID: $!"
