#!/bin/bash
# Acme Lab CI/CD Test Suite
# Runs against DEBUG_PINKY mode for speed.

VENV="./.venv/bin/python3"
COLOR_GREEN="\033[92m"
COLOR_RED="\033[91m"
COLOR_RESET="\033[0m"

echo -e "🧪 Running Acme Lab CI/CD Suite..."

# 1. Logic Tests (Standalone)
echo "--- [1/3] Deduplication Unit Tests ---"
$VENV src/test_dedup.py
if [ $? -eq 0 ]; then
    echo -e "${COLOR_GREEN}PASS: Deduplication Logic${COLOR_RESET}"
else
    echo -e "${COLOR_RED}FAIL: Deduplication Logic${COLOR_RESET}"
    exit 1
fi

# 2. Integration Tests (Requires Server)
echo "--- [2/3] Shutdown Integration Test ---"
echo "Starting remote server in DEBUG_PINKY mode..."
# Kill any existing ones first
ssh -i ~/.ssh/id_rsa_wsl jallred@z87-Linux.local "pkill -f acme_lab.py" || true

# Start and capture output
./run_remote.sh DEBUG_PINKY > server_boot.log 2>&1 &
RUN_PID=$!

# Wait for server readiness by polling the log
echo "Waiting for remote server to become Fully Operational (up to 40s)..."
READY=0
for i in {1..80}; do
    if grep -q "Lab is Fully Operational" server_boot.log; then
        echo "Server is fully operational."
        READY=1
        break
    fi
    sleep 0.5
done

if [ $READY -eq 0 ]; then
    echo -e "${COLOR_RED}FAIL: Server timed out during boot.${COLOR_RESET}"
    cat server_boot.log
    ssh -i ~/.ssh/id_rsa_wsl jallred@z87-Linux.local "pkill -f acme_lab.py"
    exit 1
fi

# Run the test REMOTELY
echo "Executing test_shutdown.py on remote host..."
ssh -i ~/.ssh/id_rsa_wsl jallred@z87-Linux.local "cd ~/AcmeLab && ./.venv/bin/python3 src/test_shutdown.py"
TEST_RES=$?

# Cleanup (The server might already be dead if test_shutdown worked)
echo "Ensuring remote cleanup..."
ssh -i ~/.ssh/id_rsa_wsl jallred@z87-Linux.local "pkill -f acme_lab.py" || true

if [ $TEST_RES -eq 0 ]; then
    echo -e "${COLOR_GREEN}PASS: Remote Shutdown Reflex${COLOR_RESET}"
else
    echo -e "${COLOR_RED}FAIL: Remote Shutdown Reflex${COLOR_RESET}"
    exit 1
fi

echo -e "\n${COLOR_GREEN}✨ ALL TESTS PASSED! Ready for deployment.${COLOR_RESET}"
rm server_boot.log
