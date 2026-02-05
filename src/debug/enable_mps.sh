#!/bin/bash
# 🤖 Acme Lab: NVIDIA MPS Enabler
# Automates the setup of Multi-Process Service for the 2080 Ti node.

PROJECT_ROOT="/home/jallred/Dev_Lab/HomeLabAI"
LOG_DIR="$PROJECT_ROOT/logs/mps"
PIPE_DIR="$LOG_DIR/pipe"

# 1. Clean up old instances
echo "🛑 Stopping existing MPS instances..."
pkill -f nvidia-cuda-mps 2>/dev/null
sleep 1

# 2. Prepare directories
mkdir -p "$LOG_DIR"
mkdir -p "$PIPE_DIR"

# 3. Set environment variables
export CUDA_MPS_LOG_DIRECTORY="$LOG_DIR"
export CUDA_MPS_PIPE_DIRECTORY="$PIPE_DIR"

# 4. Start daemon
echo "🚀 Starting NVIDIA MPS Daemon..."
nvidia-cuda-mps-control -d

# 5. Verify
if pgrep -f nvidia-cuda-mps-control > /dev/null; then
    echo "✅ MPS Daemon is active."
    echo "📁 Logs: $LOG_DIR"
    echo "📁 Pipe: $PIPE_DIR"
    echo ""
    echo "⚠️  IMPORTANT: You MUST set the following in your shell or script:"
    echo "   export CUDA_MPS_PIPE_DIRECTORY=$PIPE_DIR"
else
    echo "❌ Failed to start MPS Daemon."
    exit 1
fi
