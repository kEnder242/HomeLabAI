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

# [FEAT-352] Standardized Qwen-2.5 Recipe
# Optimized for Turing (RTX 2080 Ti) with 100% Prefix Caching enabled.
# Using 'llama_legacy' adapters until Qwen-native LoRAs are trained in Goal 21.
LORA_LEGACY="/speedy/models/adapters/llama_legacy"
LORA_MODULES="cli_voice_v1=$LORA_LEGACY/cli_voice_v1 shadow_brain_v2=$LORA_LEGACY/shadow_brain_v2 lab_history_v1=$LORA_LEGACY/lab_history_v1"

$LAB_VENV_PYTHON -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --load-format auto \
    --host 0.0.0.0 \
    --port 8088 \
    --served-model-name unified-base \
    --trust-remote-code \
    --gpu-memory-utilization 0.5 \
    --max-model-len 8192 \
    --enable-chunked-prefill \
    --max-num-batched-tokens 1024 \
    --max-num-seqs 4 \
    --enforce-eager \
    --attention-backend TRITON_ATTN \
    --enable-prefix-caching \
    --enable-lora \
    --max-loras 7 \
    --max-cpu-loras 10 \
    --lora-modules $LORA_MODULES \
    --enable-auto-tool-choice \
    --tool-call-parser llama3_json \
    $VLLM_EXTRA_ARGS \
    > vllm_server.log 2>&1 &

PID=$!
echo $PID > run/vllm.pid
echo "Sovereign Node launched with PID: $PID"
