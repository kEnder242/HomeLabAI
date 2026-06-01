#!/bin/bash
# SPRINT 30: GOLD MASTER BATCH RUNNER [HARD-ERROR SENTRY]
# Protocol: BKM-032 (Deferred Semantic Evaluation)
# Goal: Run the entire 'Inflection Set' with immediate failure gating.

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

BASE_DIR="/home/jallred/Dev_Lab"
export PYTHONPATH="$BASE_DIR/HomeLabAI/src:$PYTHONPATH"

VENV_PORTFOLIO="$BASE_DIR/Portfolio_Dev/.venv/bin/python3"
VENV_LAB="$BASE_DIR/HomeLabAI/.venv/bin/python3"

# Playwright & Environment Hardening
export PW_DISABLE_FORCE_GPU=1
export ELECTRON_RUN_AS_NODE=1
ulimit -s unlimited

echo "🚀 INITIATING SPRINT 30 GOLD MASTER BATCH (v6)..."
mkdir -p "$BASE_DIR/HomeLabAI/logs"

# [BKM-033] Pulse 1: Unit Sanity
echo "[1/4] Running Unit Sanity (Attendant & Liveliness)..."
stdbuf -oL $VENV_LAB "$BASE_DIR/HomeLabAI/src/attendant_liveliness.py"
if [ $? -ne 0 ]; then echo -e "${RED}❌ HARD ERROR: Attendant Liveliness Failed.${NC}"; exit 1; fi

stdbuf -oL $VENV_LAB "$BASE_DIR/HomeLabAI/src/test_liveliness.py"
if [ $? -ne 0 ]; then echo -e "${RED}❌ HARD ERROR: Lab Liveliness (WebSocket) Failed.${NC}"; exit 1; fi

echo -e "${GREEN}✅ Unit Sanity Passed.${NC}"
sleep 10

# [BKM-033] Pulse 2: Semantic Logic
echo "[2/4] Running Mock RAG & Intent Recall..."
stdbuf -oL $VENV_PORTFOLIO "$BASE_DIR/HomeLabAI/src/tests/test_intent_recall.py"
if [ $? -ne 0 ]; then echo -e "${RED}❌ HARD ERROR: Intent Recall (BKM-015.1) Failed.${NC}"; exit 1; fi

stdbuf -oL $VENV_LAB "$BASE_DIR/HomeLabAI/src/test_rag_logic.py"
if [ $? -ne 0 ]; then echo -e "${RED}❌ HARD ERROR: RAG Multi-Stage Logic Failed.${NC}"; exit 1; fi

echo -e "${GREEN}✅ Semantic Logic Passed.${NC}"
sleep 10

# [BKM-033] Pulse 3: Stress Gauntlet
echo "[3/4] Running Stress Gauntlet (Uber 5x5 - Natural Drift)..."
# We run this last as it takes 75 minutes
stdbuf -oL $VENV_PORTFOLIO "$BASE_DIR/HomeLabAI/src/debug/uber_5x5_hand_crank.py"
if [ $? -ne 0 ]; then 
    echo -e "${RED}❌ HARD ERROR: Stress Gauntlet Failed.${NC}"
    echo "Check DOM Forensic traces in the wordy log."
    exit 1
fi

echo -e "${GREEN}⭐ GOLD MASTER CERTIFIED.${NC}"
echo "[4/4] BATCH COMPLETE."
echo "📍 Wordy Output captured in HomeLabAI/logs/"
echo "📍 Perform BKM-032 Semantic Audit now."
