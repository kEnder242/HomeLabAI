#!/bin/bash
# --- vLLM Sovereign Base Startup ---
# [Task 17.2] Registry Authority Restored
MODEL_PATH=${1:-}
LAB_VENV_PYTHON=${2:-"/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3"}

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

export VLLM_ATTENTION_BACKEND=${VLLM_ATTENTION_BACKEND:-TRITON_ATTN}
export NCCL_P2P_DISABLE=${NCCL_P2P_DISABLE:-1}
export VLLM_USE_V1=${VLLM_USE_V1:-0}
export VLLM_USE_FLASHINFER_BFLOAT16=0
export VLLM_USE_FLASHINFER_SAMPLER=0

LORA_LEGACY="/speedy/models/adapters"
LORA_MODULES="cli_voice_v1=$LORA_LEGACY/cli_voice_v1 shadow_brain_v2=$LORA_LEGACY/shadow_brain_v2 lab_history_v1=$LORA_LEGACY/lab_history_v1"

# [Task 17.2] Architecture Check: Only load Llama LoRAs if using a Llama base
if [[ "$MODEL_PATH" == *"Llama"* || "$MODEL_PATH" == *"llama"* ]]; then
    LORA_ARGS="--enable-lora --max-loras 4 --max-cpu-loras 10 --lora-modules $LORA_MODULES"
else
    echo "Non-Llama architecture detected. Disabling incompatible Llama LoRA modules."
    LORA_ARGS=""
fi

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
