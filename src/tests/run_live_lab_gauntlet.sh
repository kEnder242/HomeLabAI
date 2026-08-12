#!/bin/bash
set -e

# Live-Lab Integration Gauntlet
# Tests against live endpoints: vLLM, Foyer, Prometheus, Ollama

LOGFILE=/tmp/run_live_lab_gauntlet.log
touch $LOGFILE

echo "Starting Live Lab Gauntlet at $(date)" >> $LOGFILE

cd /home/jallred/Dev_Lab/HomeLabAI/src/tests

# Test vLLM adapter swap
python test_vllm_adapter_swap.py >> $LOGFILE 2>&1
RESULT=$?
echo "Test vLLM adapter swap: $(if [ $RESULT -eq 0 ]; then echo 'PASS'; else echo 'FAIL'; fi)" >> $LOGFILE

echo "Test 2: test_rude_gauntlet.py" >> $LOGFILE
python test_rude_gauntlet.py >> $LOGFILE 2>&1
RESULT=$?
echo "Test 2: $(if [ $RESULT -eq 0 ]; then echo 'PASS'; else echo 'FAIL'; fi)" >> $LOGFILE

echo "Test 3: test_live_fire_triage.py" >> $LOGFILE
python test_live_fire_triage.py >> $LOGFILE 2>&1
RESULT=$?
echo "Test 3: $(if [ $RESULT -eq 0 ]; then echo 'PASS'; else echo 'FAIL'; fi)" >> $LOGFILE

echo "Test 4: live_fire_integration.py" >> $LOGFILE
python live_fire_integration.py >> $LOGFILE 2>&1
RESULT=$?
echo "Test 4: $(if [ $RESULT -eq 0 ]; then echo 'PASS'; else echo 'FAIL'; fi)" >> $LOGFILE

echo "Gauntlet complete at $(date)" >> $LOGFILE

cat $LOGFILE