#!/bin/bash

# Configuration
VENV_PATH="/home/jallred/Dev_Lab/HomeLabAI/.venv"
VLLM_PID_FILE="/home/jallred/Dev_Lab/HomeLabAI/server_vllm.pid"
START_VLLM="/home/jallred/Dev_Lab/HomeLabAI/src/start_vllm.sh"

function stop_vllm() {
    echo "Stopping vLLM engine..."
    if [ -f "$VLLM_PID_FILE" ]; then
        PID=$(cat "$VLLM_PID_FILE")
        kill $PID 2>/dev/null
        rm "$VLLM_PID_FILE"
    fi
    pkill -f vllm_liger_server.py 2>/dev/null
    pkill -f VLLM::EngineCore 2>/dev/null
}

function stop_ollama() {
    echo "Stopping Ollama service..."
    sudo systemctl stop ollama 2>/dev/null || pkill ollama 2>/dev/null
}

function start_ollama() {
    echo "Starting Ollama service..."
    sudo systemctl start ollama 2>/dev/null
}

case "$1" in
    vllm)
        echo "--- SWITCHING TO VLLM ---"
        stop_ollama
        sleep 2
        bash "$START_VLLM"
        ;;
    ollama)
        echo "--- SWITCHING TO OLLAMA ---"
        stop_vllm
        sleep 2
        start_ollama
        ;;
    status)
        echo "--- ENGINE STATUS ---"
        if lsof -i :8088 > /dev/null; then echo "vLLM: ONLINE (8088)"; else echo "vLLM: OFFLINE"; fi
        if lsof -i :11434 > /dev/null; then echo "Ollama: ONLINE (11434)"; else echo "Ollama: OFFLINE"; fi
        ;;
    *)
        echo "Usage: $0 {vllm|ollama|status}"
        exit 1
esac
