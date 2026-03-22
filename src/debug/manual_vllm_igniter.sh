#!/bin/bash
# Standalone vLLM Launcher for Forensic Audit
export VLLM_USE_V1=1
export NCCL_P2P_DISABLE=1

# Use absolute path for log and capture ALL output (&>)
/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3 -m vllm.entrypoints.openai.api_server \
    --model "/speedy/models/llama-3.2-3b-instruct-awq" \
    --host 0.0.0.0 --port 8088 \
    --served-model-name unified-base \
    --gpu-memory-utilization 0.5 \
    --enforce-eager \
    --enable-lora --max-loras 4 \
    --lora-modules lab_sentinel_v1=/speedy/models/adapters/lab_sentinel_v1 cli_voice_v1=/speedy/models/adapters/cli_voice_v1 shadow_brain_v2=/speedy/models/adapters/shadow_brain_v2 lab_history_v1=/speedy/models/adapters/lab_history_v1 \
    &> /home/jallred/Dev_Lab/HomeLabAI/vllm_manual.log &

echo "Detached Engine Ignition Initiated. PID: $!"
