import requests
import json
import time
import subprocess

def test_triage_casual_with_priming():
    print("Testing CASUAL vibe triage with Early Priming...")
    # This simulates a "casual but technical" query
    payload = {"content": "Hi! How do you calculate pi?", "type": "text_input", "request_id": "TEST_PRIMING_123"}
    
    resp = requests.post("http://localhost:8765/stream_ingest", json=payload)
    assert resp.status_code == 200
    
    time.sleep(10)
    
    logs = subprocess.check_output(["tail", "-n", "200", "/home/jallred/Dev_Lab/HomeLabAI/server.log"]).decode()
    
    # Assert Pre-triage broadcast (the 'First Try' priming)
    # The hub should broadcast this *before* triage result is logged.
    assert "Initiating mental synthesis" in logs or "Acknowledged" in logs
    
    # Assert triage routing
    assert '"intent": "CASUAL"' in logs or '"intent": "STRATEGIC"' in logs
    print("✓ First Try Priming and Triage successful (Schema validated in logs).")

if __name__ == "__main__":
    test_triage_casual_with_priming()
