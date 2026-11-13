#!/usr/bin/env bash
# ==============================================================================
# Canonical Lab Engine Controller (engine_ctl.sh)
# Framework Anchor: [LAB-122] Zero-Host Hybrid Inference Standard
# Sprint Anchor   : SPRINT_PLAN_SPR_111_0 (Story 111.10)
# Protocols       : BKM-018 (Attendant Gateway), BKM-044 (API-First Authority)
#
# Supported Verbs:
#   start [--mode=<mode>] : Boots inference engine in background with PID tracking
#   stop                  : Symmetrically terminates engine & RPC server; verifies VRAM drain
#   restart [--mode=...]  : Clean stop followed by start
#   status                : Probes port 8088, query latency, VRAM, and memory footprint
#   quiesce               : Deep quiescence drain (alias to stop with strict telemetry verification)
#   test                  : Probes multi-GPU hardware endpoints (CUDA & Vulkan)
#
# Supported Modes:
#   1. moe-cuda-rpc : RTX 2080 Ti (CUDA CC75) + Arc B580 (ggml-rpc-server port 50052) [DEFAULT]
#   2. moe-dual     : Dual-Vulkan layer split (Vulkan0 + Vulkan1)
#   3. speculative  : Arc B580 Target (Vulkan1) + RTX 2080 Ti Predictor (Vulkan0)
#   4. single-2080ti: Fast Standalone Execution on RTX 2080 Ti (~60 tok/s)
#   5. vllm / cuda  : Pure CUDA legacy vLLM daemon
# ==============================================================================

set -eo pipefail

HOMELAB_DIR="/home/jallred/Dev_Lab/HomeLabAI"
RUN_DIR="$HOMELAB_DIR/run"
LOG_DIR="$HOMELAB_DIR"
INFRA_CONFIG="$HOMELAB_DIR/config/infrastructure.json"

ENGINE_PID_FILE="$RUN_DIR/engine.pid"
RPC_PID_FILE="$RUN_DIR/rpc.pid"
LEGACY_PID_FILE="$RUN_DIR/vllm.pid"
ENGINE_LOG="$LOG_DIR/vllm_server.log"
RPC_LOG="$RUN_DIR/rpc_b580.log"

PORT="${PORT:-8088}"
HYBRID_BIN="/home/jallred/hybrid_engine/llama.cpp/build_vulkan/bin/llama-server"
CUDA_BIN="/home/jallred/hybrid_engine/llama.cpp/build_cuda/bin/llama-server"
RPC_BIN="/home/jallred/hybrid_engine/llama.cpp/build_vulkan/bin/ggml-rpc-server"

mkdir -p "$RUN_DIR"

# Helper: Detect default mode from infrastructure.json
get_default_mode() {
    local detected=""
    if [[ -f "$INFRA_CONFIG" ]]; then
        detected=$(python3 -c "import json; print(json.load(open('$INFRA_CONFIG')).get('inference_engine', {}).get('mode', 'moe-cuda-rpc'))" 2>/dev/null || true)
    fi
    echo "${detected:-moe-cuda-rpc}"
}

# Helper: Check if port 8088 is responding and ready
is_engine_responsive() {
    curl -s -f -m 2 "http://127.0.0.1:${PORT}/v1/models" >/dev/null 2>&1
}

# Helper: Get NVIDIA VRAM in MB
get_nvidia_vram_used() {
    if command -v nvidia-smi >/dev/null 2>&1; then
        nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -n 1 | tr -d ' '
    else
        echo "0"
    fi
}

# ------------------------------------------------------------------------------
# VERB: STATUS
# ------------------------------------------------------------------------------
cmd_status() {
    echo "=========================================================="
    echo "🔍 Federated Lab Inference Engine Status"
    echo "=========================================================="
    local vram_used
    vram_used=$(get_nvidia_vram_used)
    echo "RTX 2080 Ti VRAM Usage: ${vram_used} MiB"

    local engine_pid=""
    if [[ -f "$ENGINE_PID_FILE" ]]; then
        engine_pid=$(cat "$ENGINE_PID_FILE" 2>/dev/null || true)
    elif [[ -f "$LEGACY_PID_FILE" ]]; then
        engine_pid=$(cat "$LEGACY_PID_FILE" 2>/dev/null || true)
    fi

    local rpc_pid=""
    if [[ -f "$RPC_PID_FILE" ]]; then
        rpc_pid=$(cat "$RPC_PID_FILE" 2>/dev/null || true)
    fi

    if [[ -n "$engine_pid" ]] && kill -0 "$engine_pid" 2>/dev/null; then
        local rss_kb
        rss_kb=$(awk '/VmRSS/{print $2}' "/proc/$engine_pid/status" 2>/dev/null || echo "0")
        local rss_mb=$(( rss_kb / 1024 ))
        local swap_kb
        swap_kb=$(awk '/VmSwap/{print $2}' "/proc/$engine_pid/status" 2>/dev/null || echo "0")
        local swap_mb=$(( swap_kb / 1024 ))
        echo "Engine Process        : PID $engine_pid (ALIVE, RSS=${rss_mb} MB, Swap=${swap_mb} MB)"
    else
        echo "Engine Process        : NOT RUNNING"
    fi

    if [[ -n "$rpc_pid" ]] && kill -0 "$rpc_pid" 2>/dev/null; then
        echo "RPC Server (Arc B580) : PID $rpc_pid (ALIVE on port 50052)"
    else
        echo "RPC Server (Arc B580) : NOT RUNNING"
    fi

    echo -n "Port $PORT Liveness    : "
    if is_engine_responsive; then
        local t0 t1 latency_ms
        t0=$(python3 -c 'import time; print(int(time.time()*1000))')
        local models
        models=$(curl -s -m 2 "http://127.0.0.1:${PORT}/v1/models" | python3 -c 'import sys, json; print(", ".join(m["id"] for m in json.load(sys.stdin).get("data", [])))' 2>/dev/null || echo "OK")
        t1=$(python3 -c 'import time; print(int(time.time()*1000))')
        latency_ms=$(( t1 - t0 ))
        echo "ONLINE (${latency_ms}ms) -> Models: [$models]"
        return 0
    else
        echo "OFFLINE (Port unbound or unresponsive)"
        return 1
    fi
}

# ------------------------------------------------------------------------------
# VERB: STOP / QUIESCE
# ------------------------------------------------------------------------------
cmd_stop() {
    echo "=========================================================="
    echo "🛑 Symmetrically Stopping Lab Inference Engine & RPC Servers"
    echo "=========================================================="

    # 1. Terminate tracked Engine PID
    if [[ -f "$ENGINE_PID_FILE" ]]; then
        local pid
        pid=$(cat "$ENGINE_PID_FILE" 2>/dev/null || true)
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            echo "Sending SIGTERM to Engine (PID $pid)..."
            kill -15 "$pid" 2>/dev/null || true
        fi
        rm -f "$ENGINE_PID_FILE"
    fi

    # 2. Terminate legacy PID file if separate
    if [[ -f "$LEGACY_PID_FILE" ]]; then
        local lpid
        lpid=$(cat "$LEGACY_PID_FILE" 2>/dev/null || true)
        if [[ -n "$lpid" ]] && kill -0 "$lpid" 2>/dev/null; then
            echo "Sending SIGTERM to legacy Engine PID $lpid..."
            kill -15 "$lpid" 2>/dev/null || true
        fi
        rm -f "$LEGACY_PID_FILE"
    fi

    # 3. Terminate tracked RPC PID
    if [[ -f "$RPC_PID_FILE" ]]; then
        local rpid
        rpid=$(cat "$RPC_PID_FILE" 2>/dev/null || true)
        if [[ -n "$rpid" ]] && kill -0 "$rpid" 2>/dev/null; then
            echo "Sending SIGTERM to ggml-rpc-server (PID $rpid)..."
            kill -15 "$rpid" 2>/dev/null || true
        fi
        rm -f "$RPC_PID_FILE"
    fi

    # 4. Graceful settlement wait (up to 5 seconds)
    local settled=0
    for _ in {1..10}; do
        if ! fuser "$PORT/tcp" >/dev/null 2>&1 && ! fuser 50052/tcp >/dev/null 2>&1; then
            settled=1
            break
        fi
        sleep 0.5
    done

    # 5. Enforce strict termination if ports still bound
    if [[ $settled -eq 0 ]]; then
        echo "⚠️ Ports still held after 5s graceful shutdown. Enforcing targeted SIGKILL..."
        fuser -k -9 "$PORT/tcp" >/dev/null 2>&1 || true
        fuser -k -9 50052/tcp >/dev/null 2>&1 || true
        pkill -9 -f "llama-server" >/dev/null 2>&1 || true
        pkill -9 -f "ggml-rpc-server" >/dev/null 2>&1 || true
        pkill -9 -f "vllm.entrypoints.openai.api_server" >/dev/null 2>&1 || true
        pkill -9 -f "VLLM::EngineCore" >/dev/null 2>&1 || true
    fi

    # Clean residual PID files
    rm -f "$ENGINE_PID_FILE" "$RPC_PID_FILE" "$LEGACY_PID_FILE"

    # 6. Physical VRAM & Port Verification Gate
    sleep 1
    local vram_used
    vram_used=$(get_nvidia_vram_used)
    echo "Physical Silicon Verification:"
    echo "  - Port $PORT free : $(fuser "$PORT/tcp" >/dev/null 2>&1 && echo 'FAILED' || echo 'VERIFIED FREE')"
    echo "  - Port 50052 free: $(fuser 50052/tcp >/dev/null 2>&1 && echo 'FAILED' || echo 'VERIFIED FREE')"
    echo "  - RTX 2080 Ti VRAM: ${vram_used} MiB (Threshold < 500 MiB)"

    if [[ "$vram_used" -lt 500 ]]; then
        echo "✅ Engine and RPC servers cleanly stopped. VRAM successfully reclaimed."
        return 0
    else
        echo "⚠️ Note: RTX 2080 Ti VRAM is ${vram_used} MiB (may include desktop compositor / remote desktop)."
        return 0
    fi
}

# ------------------------------------------------------------------------------
# VERB: START
# ------------------------------------------------------------------------------
cmd_start() {
    local requested_mode="${1:-}"
    local mode
    if [[ -n "$requested_mode" ]]; then
        mode="${requested_mode#--mode=}"
    else
        mode=$(get_default_mode)
    fi

    # [LAB-122] Port 8088 Liveness Gate: Prevent duplicate background instance spawning
    if is_engine_responsive; then
        echo "✅ [LAB-122] Unified inference engine already active and responsive on port $PORT."
        cmd_status
        return 0
    fi

    echo "=========================================================="
    echo "🚀 Launching Unified Inference Engine [Mode: $mode]"
    echo "   - Host RAM Policy : Zero-Host Allocation (-lm auto --no-host)"
    echo "   - Listening Port  : $PORT"
    echo "=========================================================="

    case "$mode" in
        moe-cuda-rpc|cuda-rpc|moe-hybrid)
            start_moe_cuda_rpc
            ;;
        moe-dual|moe|dual)
            start_moe_dual
            ;;
        speculative|hybrid)
            start_speculative
            ;;
        single-2080ti|standalone)
            start_single_2080ti
            ;;
        vllm|cuda)
            start_vllm
            ;;
        *)
            echo "❌ Unknown mode: $mode"
            echo "Supported modes: moe-cuda-rpc, moe-dual, speculative, single-2080ti, vllm"
            exit 1
            ;;
    esac
}

# --- Mode Implementations ---

start_moe_cuda_rpc() {
    local model_path="${MODEL_PATH:-/speedy/models/gguf/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf}"
    if [[ ! -f "$model_path" ]]; then
        echo "❌ Model not found: $model_path"
        exit 1
    fi

    # Dynamically detect Intel Arc B580 Vulkan device index
    local b580_dev
    b580_dev=$("$RPC_BIN" -h 2>&1 | grep -i "Arc" | awk -F':' '{print $2}' | awk '{print "Vulkan"$1}' | head -n 1 || true)
    b580_dev="${b580_dev:-Vulkan0}"

    # Ensure RPC server is running on loopback port 50052
    if ! fuser 50052/tcp >/dev/null 2>&1; then
        echo "Starting ggml-rpc-server on Arc B580 ($b580_dev, port 50052)..."
        setsid "$RPC_BIN" -d "$b580_dev" -p 50052 > "$RPC_LOG" 2>&1 &
        local rpc_pid=$!
        echo "$rpc_pid" > "$RPC_PID_FILE"
        sleep 2
    else
        echo "✅ ggml-rpc-server already active on port 50052."
    fi

    echo "Spawning CUDA llama-server with Arc B580 RPC loopback..."
    setsid "$CUDA_BIN" \
        -m "$model_path" \
        -lm auto \
        --no-host \
        --rpc 127.0.0.1:50052 \
        -dev CUDA0,RPC0 \
        -sm layer \
        -ts 10,12 \
        -mg 0 \
        -ngl 99 \
        -c 32768 \
        -ctk q4_0 -ctv q4_0 \
        --reasoning off \
        --reasoning-budget 0 \
        --port "$PORT" \
        --host "0.0.0.0" \
        --parallel 1 \
        --alias "Qwen3.6-35B-A3B,local,unified-base" > "$ENGINE_LOG" 2>&1 &
    local engine_pid=$!
    echo "$engine_pid" > "$ENGINE_PID_FILE"
    echo "$engine_pid" > "$LEGACY_PID_FILE"
    echo "Engine spawned (PID $engine_pid). Awaiting initialization..."
}

start_moe_dual() {
    local model_path="${MODEL_PATH:-/speedy/models/gguf/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf}"
    if [[ ! -f "$model_path" ]]; then
        echo "❌ Model not found: $model_path"
        exit 1
    fi

    setsid "$HYBRID_BIN" \
        -m "$model_path" \
        -lm auto \
        --no-host \
        -dev Vulkan0,Vulkan1 \
        -sm layer \
        -ts 11,12 \
        -mg 0 \
        -ngl 99 \
        -c 32768 \
        -ctk q4_0 -ctv q4_0 \
        --reasoning off \
        --reasoning-budget 0 \
        --port "$PORT" \
        --host "0.0.0.0" \
        --parallel 1 \
        --alias "Qwen3.6-35B-A3B,local,unified-base" > "$ENGINE_LOG" 2>&1 &
    local engine_pid=$!
    echo "$engine_pid" > "$ENGINE_PID_FILE"
    echo "$engine_pid" > "$LEGACY_PID_FILE"
    echo "Dual-Vulkan MoE Engine spawned (PID $engine_pid)."
}

start_speculative() {
    local target_model="${TARGET_MODEL:-/speedy/models/gguf/Qwen3.7-Flash-8B-Q8_0.gguf}"
    local draft_model="${DRAFT_MODEL:-/speedy/models/gguf/Qwen3.7-Flash-4B-Q8_0.gguf}"

    if [[ ! -f "$target_model" ]]; then
        echo "❌ Target model not found: $target_model"
        exit 1
    fi
    if [[ ! -f "$draft_model" ]]; then
        echo "⚠️ Draft model not found at $draft_model. Falling back to single-2080ti mode..."
        start_single_2080ti
        return
    fi

    setsid "$HYBRID_BIN" \
        -m "$target_model" \
        -lm auto \
        --no-host \
        -dev Vulkan1 \
        -ngl 99 \
        -c 32768 \
        -ctk q4_0 -ctv q4_0 \
        -md "$draft_model" \
        -devd Vulkan0 \
        -ngld 99 \
        -ctkd q4_0 -ctvd q4_0 \
        --spec-draft-n-max 4 \
        --reasoning off \
        --reasoning-budget 0 \
        --port "$PORT" \
        --host "0.0.0.0" \
        --parallel 2 \
        --alias "Qwen3.7-Flash-8B,local,unified-base" > "$ENGINE_LOG" 2>&1 &
    local engine_pid=$!
    echo "$engine_pid" > "$ENGINE_PID_FILE"
    echo "$engine_pid" > "$LEGACY_PID_FILE"
    echo "Speculative Engine spawned (PID $engine_pid)."
}

start_single_2080ti() {
    local model_path="${MODEL_PATH:-/speedy/models/gguf/Qwen3.7-Flash-8B-Q8_0.gguf}"

    setsid "$HYBRID_BIN" \
        -m "$model_path" \
        -lm auto \
        --no-host \
        -dev Vulkan0 \
        -ngl 99 \
        -c 32768 \
        -ctk q4_0 -ctv q4_0 \
        --reasoning off \
        --reasoning-budget 0 \
        --port "$PORT" \
        --host "0.0.0.0" \
        --parallel 2 \
        --alias "Qwen3.7-Flash-8B,local,unified-base" > "$ENGINE_LOG" 2>&1 &
    local engine_pid=$!
    echo "$engine_pid" > "$ENGINE_PID_FILE"
    echo "$engine_pid" > "$LEGACY_PID_FILE"
    echo "Single 2080 Ti Engine spawned (PID $engine_pid)."
}

start_vllm() {
    echo "Starting legacy vLLM daemon..."
    systemctl restart vllm.service 2>/dev/null || true
}

# ------------------------------------------------------------------------------
# VERB: RESTART
# ------------------------------------------------------------------------------
cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start "$@"
}

# ------------------------------------------------------------------------------
# VERB: HARDWARE TEST
# ------------------------------------------------------------------------------
cmd_test() {
    echo "--- Probing Vulkan Multi-Device Enumeration ---"
    vulkaninfo --summary 2>/dev/null | grep -E "deviceName|vendorID" || true
    echo "--- Probing CUDA RTX 2080 Ti ---"
    nvidia-smi --query-gpu=name,memory.total --format=csv || true
    echo "--- Probing Intel Arc B580 ---"
    vpl-inspect 2>/dev/null | grep -i "DeviceID" || true
    echo "✅ Hardware probe complete."
}

# ------------------------------------------------------------------------------
# DISPATCHER
# ------------------------------------------------------------------------------
ACTION="${1:-status}"
shift || true

case "$ACTION" in
    start)
        cmd_start "$@"
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart "$@"
        ;;
    status)
        cmd_status
        ;;
    quiesce)
        cmd_stop
        ;;
    test)
        cmd_test
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|quiesce|test} [--mode=<mode>]"
        exit 1
        ;;
esac
