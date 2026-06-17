#!/bin/bash
# --- vLLM Sovereign Base Startup (Llama-3.2-3B-Instruct-AWQ) ---
# [FEAT-145] Unified Sovereign Environment (Stable Baseline)
MODEL_PATH=$1
LAB_VENV_PYTHON=$2

if [ -z "$LAB_VENV_PYTHON" ]; then
    LAB_VENV_PYTHON="/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3"
fi

# Fallback to the stable Llama-3.2-3B base model
if [ -z "$MODEL_PATH" ]; then
    MODEL_PATH="/speedy/models/llama-3.2-3b-instruct-awq"
fi

# [TURING BREAKTHROUGH] Optimization Defaults for RTX 2080 Ti
export VLLM_ATTENTION_BACKEND=${VLLM_ATTENTION_BACKEND:-TRITON_ATTN}
export NCCL_P2P_DISABLE=${NCCL_P2P_DISABLE:-1}
export VLLM_USE_V1=${VLLM_USE_V1:-0}
export VLLM_USE_FLASHINFER_BFLOAT16=0  # [TURING FIX] Disable BF16 JIT
export VLLM_USE_FLASHINFER_SAMPLER=0   # [TURING FIX] Disable FlashInfer Sampler

echo "--- vLLM Sovereign Ignition: $MODEL_PATH ---"
LORA_LEGACY="/speedy/models/adapters/llama_legacy"
LORA_MODULES="cli_voice_v1=$LORA_LEGACY/cli_voice_v1 shadow_brain_v2=$LORA_LEGACY/shadow_brain_v2 lab_history_v1=$LORA_LEGACY/lab_history_v1"

# Enable LoRA modules for stable Llama environment
LORA_ARGS="--enable-lora --max-loras 4 --max-cpu-loras 10 --lora-modules $LORA_MODULES"

# [Task 7.1] Physics: Fix fragmented JIT paths after driver upgrade
CUDA_LIB_PATH="/home/jallred/Dev_Lab/HomeLabAI/.venv/lib/python3.12/site-packages/nvidia/cu13/lib"
export LD_LIBRARY_PATH="$CUDA_LIB_PATH:$LD_LIBRARY_PATH"

$LAB_VENV_PYTHON -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --load-format auto \
    --host 0.0.0.0 \
    --port 8088 \
    --served-model-name unified-base \
    --trust-remote-code \
    --gpu-memory-utilization 0.4 \
    --max-model-len 8192 \
    --enable-chunked-prefill \
    --max-num-batched-tokens 1024 \
    --max-num-seqs 16 \
    --enforce-eager \
    --attention-backend TRITON_ATTN \
    --enable-prefix-caching \
    $LORA_ARGS \
    $VLLM_EXTRA_ARGS \
    > /home/jallred/Dev_Lab/HomeLabAI/vllm_server.log 2>&1 &

PID=$!
echo $PID > /home/jallred/Dev_Lab/HomeLabAI/run/vllm.pid
echo "Sovereign Node launched with PID: $PID"
