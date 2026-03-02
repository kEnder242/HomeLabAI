#!/bin/bash
# --- vLLM 0.16.0 Laboratory Launcher (Plan A: SDPA Baseline) ---
export VLLM_ATTENTION_BACKEND=TORCH_SDPA
export NCCL_P2P_DISABLE=1 
export VLLM_USE_V1=1
export PYTHONPATH=$PYTHONPATH:$(pwd)/HomeLabAI/src

VENV_PYTHON="/home/jallred/Dev_Lab/.venv_vllm_016/bin/python3"
MODEL="/speedy/models/Qwen2.5-3B-Instruct"

echo "--- 🚀 Launching vLLM 0.16.0 (Plan A - SDPA): $MODEL ---"

$VENV_PYTHON -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --dtype float16 \
    --attention-backend torch_sdpa \
    --enforce-eager \
    --gpu-memory-utilization 0.7 \
    --max-model-len 4096 \
    --port 8088 \
    --served-model-name vllm-016-bench \
    --trust-remote-code \
    > HomeLabAI/vllm_016_bench.log 2>&1 &

echo "Server backgrounded. Tailing HomeLabAI/vllm_016_bench.log..."
