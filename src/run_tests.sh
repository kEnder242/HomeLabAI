#!/bin/bash
# Acme Lab CI/CD Test Suite
# Usage: ./run_tests.sh [--full]

MODE="FAST"
if [ "$1" == "--full" ]; then
    MODE="FULL"
fi

VENV="./.venv/bin/python3"
COLOR_GREEN="\033[92m"
COLOR_YELLOW="\033[93m"
COLOR_RED="\033[91m"
COLOR_RESET="\033[0m"

echo -e "🧪 Running Acme Lab CI/CD Suite (Mode: $MODE)..."

# 1. Logic Tests (Always Run)
echo "--- [1/3] Fast Logic Tests (<5s) ---"
$VENV src/test_dedup.py
if [ $? -ne 0 ]; then
    echo -e "${COLOR_RED}FAIL: Deduplication Logic${COLOR_RESET}"
    exit 1
fi
echo -e "${COLOR_GREEN}PASS: Unit Tests${COLOR_RESET}"

# 1.5 Mock Integration (Tics)
echo "--- [2/3] Mock Integration (Nervous Tics) ---"
echo "Starting remote server in MOCK_BRAIN mode (Tmux)..."
./src/start_server_fast.sh MOCK_BRAIN

# Wait for readiness (poll tmux pane)
echo "Waiting for Mock Server..."
READY=0
for i in {1..20}; do
    ssh -i ~/.ssh/id_rsa_wsl jallred@z87-Linux.local "tmux capture-pane -pt acme_fast" | grep "Lab is Fully Operational" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        READY=1
        break
    fi
    sleep 0.5
done
TIC_RES=$?
ssh -i ~/.ssh/id_rsa_wsl jallred@z87-Linux.local "pkill -f acme_lab.py" || true
rm server_boot_mock.log

if [ $TIC_RES -ne 0 ]; then
    echo -e "${COLOR_RED}FAIL: Nervous Tic Test${COLOR_RESET}"
    exit 1
fi
echo -e "${COLOR_GREEN}PASS: Nervous Tic Logic${COLOR_RESET}"

# Future: Add Mock Integration here (MOCK_BRAIN)
# For now, we only have Real Integration, so we skip it in FAST mode
if [ "$MODE" == "FAST" ]; then
    echo -e "${COLOR_YELLOW}SKIP: Cognitive Integration Tests (Use --full to run)${COLOR_RESET}"
    echo -e "\n${COLOR_GREEN}✨ FAST CHECKS PASSED!${COLOR_RESET}"
    exit 0
fi

# 2. Integration Tests (Requires Real Server)
echo "--- [3/3] Cognitive Integration Tests (>30s) ---"
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

echo -e "\n${COLOR_GREEN}✨ FULL SUITE PASSED!${COLOR_RESET}"
rm server_boot.log
