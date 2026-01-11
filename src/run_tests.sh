#!/bin/bash
# Acme Lab CI/CD Test Suite (Refactored)
# Usage: ./src/run_tests.sh

COLOR_GREEN="\033[92m"
COLOR_YELLOW="\033[93m"
COLOR_RED="\033[91m"
COLOR_RESET="\033[0m"

HOST_DNS="z87-Linux.local"

# 1. Resolve IP
echo "🔍 Resolving $HOST_DNS..."
HOST_IP=$(ping -c 1 $HOST_DNS | head -n 1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+')
if [ -z "$HOST_IP" ]; then
    echo -e "\n${COLOR_RED}❌ Failed to resolve $HOST_DNS.${COLOR_RESET}"
    exit 1
fi
echo "✅ Resolved to: $HOST_IP"
TARGET="jallred@$HOST_IP"

echo -e "🧪 Running Acme Lab CI/CD Suite..."

# 2. Sync Code
./sync_to_linux.sh

# 3. Start Server (Mock Brain Mode for Speed)
echo "🚀 Starting Remote Server (MOCK_BRAIN) via Tmux..."
./src/start_server_fast.sh MOCK_BRAIN

# 4. Wait for Readiness (Socket Poll)
echo "⏳ Waiting for Lab Readiness (Polling Socket)..."
MAX_RETRIES=40
READY=0
for i in $(seq 1 $MAX_RETRIES); do
    ssh -i ~/.ssh/id_rsa_wsl "$TARGET" "nc -zv 127.0.0.1 8765" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        READY=1
        echo "✅ Server is listening!"
        break
    fi
    echo -n "."
    sleep 2
done

if [ $READY -eq 0 ]; then
    echo -e "\n${COLOR_RED}❌ FAIL: Server failed to start.${COLOR_RESET}"
    exit 1
fi

# 5. Run Tests
FAIL=0

# Helper to restart server
function restart_server {
    echo "🔄 Restarting Server..."
    ssh -i ~/.ssh/id_rsa_wsl "$TARGET" "tmux kill-session -t acme_fast 2>/dev/null"
    ./src/start_server_fast.sh MOCK_BRAIN
    
    echo "⏳ Waiting for Lab Readiness..."
    for i in $(seq 1 $MAX_RETRIES); do
        ssh -i ~/.ssh/id_rsa_wsl "$TARGET" "nc -zv 127.0.0.1 8765" > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            return 0
        fi
        sleep 1
    done
    return 1
}

echo -e "\n--- [TEST 1] Intercom Protocol ---"
ssh -i ~/.ssh/id_rsa_wsl "$TARGET" "cd ~/AcmeLab && ./.venv/bin/python3 src/test_intercom_flow.py"
if [ $? -ne 0 ]; then FAIL=1; fi

restart_server

echo -e "\n--- [TEST 2] Memory Integration ---"
ssh -i ~/.ssh/id_rsa_wsl "$TARGET" "cd ~/AcmeLab && ./.venv/bin/python3 src/test_memory_integration.py"
if [ $? -ne 0 ]; then FAIL=1; fi

# 6. Cleanup
echo -e "\n🧹 Cleaning up..."
ssh -i ~/.ssh/id_rsa_wsl "$TARGET" "tmux kill-session -t acme_fast"

if [ $FAIL -eq 0 ]; then
    echo -e "${COLOR_GREEN}✨ ALL TESTS PASSED!${COLOR_RESET}"
    exit 0
else
    echo -e "${COLOR_RED}💀 SOME TESTS FAILED.${COLOR_RESET}"
    exit 1
fi
