#!/bin/bash
# --- vLLM Sovereign Base Startup (Qwen-2.5-3B-Instruct) ---
# [FEAT-145] Unified Sovereign Environment
MODEL_PATH=$1
LAB_VENV_PYTHON=$2

if [ -z "$LAB_VENV_PYTHON" ]; then
    LAB_VENV_PYTHON="/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3"
fi

# Check if MODEL_PATH was passed, otherwise pull from config
if [ -z "$MODEL_PATH" ]; then
    MODEL_KEY=$(python3 -c "import json; print(json.load(open('/home/jallred/Dev_Lab/HomeLabAI/config/infrastructure.json'))['model_manifest']['unified-base'])" 2>/dev/null)
    # If unified-base points to a specific model key, resolve it
    if [[ "$MODEL_KEY" != /* ]]; then
        MODEL_PATH=$(python3 -c "import json; print(json.load(open('/home/jallred/Dev_Lab/HomeLabAI/config/infrastructure.json'))['model_manifest'].get('$MODEL_KEY', '$MODEL_KEY'))" 2>/dev/null)
    else
        MODEL_PATH=$MODEL_KEY
    fi
    
    # Fallback if config parsing fails
    if [ -z "$MODEL_PATH" ]; then
        MODEL_PATH="/speedy/models/llama-3.2-3b-instruct-awq"
    fi
fi

# [TURING BREAKTHROUGH] Optimization Defaults for RTX 2080 Ti
# These can be overridden by the Lab Attendant (V3) environment.
export VLLM_ATTENTION_BACKEND=${VLLM_ATTENTION_BACKEND:-TRITON_ATTN}
export NCCL_P2P_DISABLE=${NCCL_P2P_DISABLE:-1}
export VLLM_USE_V1=${VLLM_USE_V1:-0}
export VLLM_USE_FLASHINFER_BFLOAT16=0  # [TURING FIX] Disable BF16 JIT
export VLLM_USE_FLASHINFER_SAMPLER=0   # [TURING FIX] Disable FlashInfer Sampler

echo "--- vLLM Sovereign Ignition: $MODEL_PATH ---"
echo "Env: Backend=${VLLM_ATTENTION_BACKEND}, P2P_Disable=${NCCL_P2P_DISABLE}, V1=${VLLM_USE_V1}"
# [FEAT-352] Standardized Llama-3.2 Recipe
# Optimized for Turing (RTX 2080 Ti) with 100% Prefix Caching enabled.
LORA_LEGACY="/speedy/models/adapters/llama_legacy"
LORA_MODULES="cli_voice_v1=$LORA_LEGACY/cli_voice_v1 shadow_brain_v2=$LORA_LEGACY/shadow_brain_v2 lab_history_v1=$LORA_LEGACY/lab_history_v1"

# [Task 16.1] If using Qwen, disable LoRA modules to prevent architecture mismatch crash.
if [[ "$MODEL_PATH" == *"Qwen"* || "$MODEL_PATH" == *"qwen"* ]]; then
    echo "Qwen architecture detected. Disabling incompatible Llama LoRA modules."
    LORA_ARGS=""
else
    LORA_ARGS="--enable-lora --max-loras 4 --max-cpu-loras 10 --lora-modules $LORA_MODULES"
fi

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
