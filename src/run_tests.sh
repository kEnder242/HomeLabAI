#!/bin/bash
# Acme Lab CI/CD Test Suite (Refactored)
# Usage: ./src/run_tests.sh

COLOR_GREEN="\033[92m"
COLOR_YELLOW="\033[93m"
COLOR_RED="\033[91m"
COLOR_RESET="\033[0m"

echo -e "🧪 Running Acme Lab CI/CD Suite..."

# 1. Sync Code
./sync_to_linux.sh

# 2. Start Server (Mock Brain Mode for Speed)
echo "🚀 Starting Remote Server (MOCK_BRAIN) via Tmux..."
./src/start_server_fast.sh MOCK_BRAIN

# 3. Wait for Readiness (Using a Python waiter is safer than log grep)
echo "⏳ Waiting for Lab Readiness (Polling Socket)..."
# We can use one of our test scripts to poll until ready
ssh -i ~/.ssh/id_rsa_wsl jallred@192.168.1.221 "cd ~/AcmeLab && ./.venv/bin/python3 -c 'import asyncio, websockets; async def c(): async with websockets.connect(\"ws://localhost:8765\"): pass; asyncio.run(c())' 2>/dev/null"
# Loop with timeout
MAX_RETRIES=40
READY=0
for i in $(seq 1 $MAX_RETRIES); do
    ssh -i ~/.ssh/id_rsa_wsl jallred@192.168.1.221 "cd ~/AcmeLab && ./.venv/bin/python3 -c 'import asyncio, websockets; async def c(): async with websockets.connect(\"ws://localhost:8765\"): pass; asyncio.run(c())'" 2>/dev/null
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

# 4. Run Tests
FAIL=0

echo -e "\n--- [TEST 1] Intercom Protocol ---"
ssh -i ~/.ssh/id_rsa_wsl jallred@192.168.1.221 "cd ~/AcmeLab && ./.venv/bin/python3 src/test_intercom_flow.py"
if [ $? -ne 0 ]; then FAIL=1; fi

echo -e "\n--- [TEST 2] Memory Integration ---"
ssh -i ~/.ssh/id_rsa_wsl jallred@192.168.1.221 "cd ~/AcmeLab && ./.venv/bin/python3 src/test_memory_integration.py"
if [ $? -ne 0 ]; then FAIL=1; fi

# 5. Cleanup
echo -e "\n🧹 Cleaning up..."
ssh -i ~/.ssh/id_rsa_wsl jallred@192.168.1.221 "tmux kill-session -t acme_fast"

if [ $FAIL -eq 0 ]; then
    echo -e "${COLOR_GREEN}✨ ALL TESTS PASSED!${COLOR_RESET}"
    exit 0
else
    echo -e "${COLOR_RED}💀 SOME TESTS FAILED.${COLOR_RESET}"
    exit 1
fi