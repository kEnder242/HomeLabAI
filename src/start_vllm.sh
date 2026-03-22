#!/bin/bash
# --- vLLM Sovereign Base Startup (Qwen-2.5-3B-Instruct) ---
# [FEAT-145] Unified Sovereign Environment
MODEL_PATH=$1
LAB_VENV_PYTHON=$2

if [ -z "$LAB_VENV_PYTHON" ]; then
    LAB_VENV_PYTHON="/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3"
fi

if [ -z "$MODEL_PATH" ]; then
    MODEL_PATH="/speedy/models/Qwen2.5-3B-Instruct"
fi

# [TURING BREAKTHROUGH] Optimization Defaults for RTX 2080 Ti
# These can be overridden by the Lab Attendant (V3) environment.
export VLLM_ATTENTION_BACKEND=${VLLM_ATTENTION_BACKEND:-TRITON_ATTN}
export NCCL_P2P_DISABLE=${NCCL_P2P_DISABLE:-1}
export VLLM_USE_V1=${VLLM_USE_V1:-0}

echo "--- vLLM Sovereign Ignition: $MODEL_PATH ---"
echo "Env: Backend=${VLLM_ATTENTION_BACKEND}, P2P_Disable=${NCCL_P2P_DISABLE}, V1=${VLLM_USE_V1}"

# [FEAT-030] Unity Pattern: Consume VLLM_EXTRA_ARGS from lab_attendant
# Path Hardening: We assume we are running from HomeLabAI/ or its parent.
$LAB_VENV_PYTHON -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --load-format auto \
    --host 0.0.0.0 \
    --port 8088 \
    --served-model-name unified-base \
    --max-model-len 8192 \
    --trust-remote-code \
    --enable-auto-tool-choice \
    --tool-call-parser llama3_json \
    --use-v1=0 \
    $VLLM_EXTRA_ARGS \
    > vllm_server.log 2>&1 &

echo "Sovereign Node launched with PID: $!"
