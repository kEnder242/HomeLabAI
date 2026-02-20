#!/bin/bash
LOG_FILE="/home/jallred/Dev_Lab/HomeLabAI/logs/build_monitor.log"
BUILD_LOG="/home/jallred/Dev_Lab/HomeLabAI/logs/build_afk_rigor.log"
VENV="/home/jallred/Dev_Lab/.venv_v072/bin/python3"
PROJECT_DIR="/home/jallred/Dev_Lab/HomeLabAI/vendor/vllm"

echo "🛡️ Persistence Babysitter ACTIVE at $(date)" > $LOG_FILE

function restart_build() {
    echo "⚠️ RESTART TRIGGERED at $(date)" >> $LOG_FILE
    cd $PROJECT_DIR
    export MAX_JOBS=4
    export TORCH_CUDA_ARCH_LIST="7.5"
    export VLLM_INSTALL_PUNICA_KERNELS=1
    export CUDA_HOME=/usr
    nohup bash -c "export MAX_JOBS=4; export TORCH_CUDA_ARCH_LIST='7.5'; export VLLM_INSTALL_PUNICA_KERNELS=1; export CUDA_HOME=/usr; $VENV -m pip install -e ." > $BUILD_LOG 2>&1 &
}

function check_status() {
    if ps aux | grep -E "cc1plus|nvcc|ninja" | grep -v grep > /dev/null; then
        echo "✅ STATUS: Compiling. Log size: $(du -h $BUILD_LOG | awk '{print $1}')" >> $LOG_FILE
        return 0
    else
        if grep -q "Successfully installed" $BUILD_LOG; then
            echo "✨ STATUS: SUCCESS! Build complete." >> $LOG_FILE
            exit 0
        elif grep -q "ERROR" $BUILD_LOG; then
            echo "❌ STATUS: FAILURE DETECTED. Restarting build..." >> $LOG_FILE
            restart_build
            return 1 # Signal to reset interval
        else
            echo "⏳ STATUS: Idle/Stalled. Log tail: $(tail -n 1 $BUILD_LOG)" >> $LOG_FILE
            # If idle too long without success, we might need a kick, but let's be cautious
            return 0
        fi
    fi
}

# Master Loop
while true; do
    # Phase 1: 5-min checks (x2)
    for i in 1 2; do
        sleep 300
        echo "--- Heartbeat (5m) [$(date)] ---" >> $LOG_FILE
        check_status || break 2 # Reset to start of while true
    done

    # Phase 2: 15-min checks
    while true; do
        sleep 900
        echo "--- Heartbeat (15m) [$(date)] ---" >> $LOG_FILE
        check_status || break 1 # Return to outer loop (5-min phase)
    done
done
