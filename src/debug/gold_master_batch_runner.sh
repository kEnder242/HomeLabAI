#!/bin/bash
# SPRINT 30: GOLD MASTER BATCH RUNNER [FULLY HARDENED]
# Protocol: BKM-032 (Deferred Semantic Evaluation)
# Goal: Run the entire 'Inflection Set' to anchor the baseline.

BASE_DIR="/home/jallred/Dev_Lab"
export PYTHONPATH="$BASE_DIR/HomeLabAI/src:$PYTHONPATH"

VENV_PORTFOLIO="$BASE_DIR/Portfolio_Dev/.venv/bin/python3"
VENV_LAB="$BASE_DIR/HomeLabAI/.venv/bin/python3"

# Playwright & Environment Hardening
export PW_DISABLE_FORCE_GPU=1
export ELECTRON_RUN_AS_NODE=1
ulimit -s unlimited

echo "🚀 INITIATING SPRINT 30 GOLD MASTER BATCH (v5)..."
mkdir -p "$BASE_DIR/HomeLabAI/logs"

echo "[1/4] Running Unit Sanity (Attendant & Liveliness)..."
$VENV_LAB "$BASE_DIR/HomeLabAI/src/attendant_liveliness.py"
$VENV_LAB "$BASE_DIR/HomeLabAI/src/test_liveliness.py"

sleep 30 # Settle time

echo "[2/4] Running Mock RAG & Intent Recall..."
$VENV_PORTFOLIO "$BASE_DIR/HomeLabAI/src/tests/test_intent_recall.py"
sleep 30
$VENV_LAB "$BASE_DIR/HomeLabAI/src/test_rag_logic.py"

sleep 30 # Settle time

echo "[3/4] Running Stress Gauntlet (Uber 5x5)..."
# We run this last as it takes 75 minutes
$VENV_PORTFOLIO "$BASE_DIR/HomeLabAI/src/debug/uber_5x5_hand_crank.py"

echo "[4/4] BATCH COMPLETE."
echo "📍 Wordy Output captured in HomeLabAI/logs/"
echo "📍 Please perform Deferred Semantic Evaluation via BKM-032 template."
