import requests
import json
import time

def test_triage_casual():
    print("Testing CASUAL vibe triage...")
    payload = {"content": "Hello there!", "type": "text_input", "request_id": "TEST_CASUAL_123"}
    # Need to simulate a websocket request to trigger the full waterfall
    # For now, we will rely on the fact that the router calls the lab_node prompt
    # and we can verify the logged triage result in the lab-attendant journal.
    resp = requests.post("http://localhost:8765/stream_ingest", json=payload)
    assert resp.status_code == 200
    
    # Wait for processing
    time.sleep(20)
    
    # Validate result from forensic logs
    # Read the last 200 lines to be safe
    # Triage happens in the Hub (server.log), not Attendant service log.
    with open("/home/jallred/Dev_Lab/HomeLabAI/server.log", "r") as f:
        logs = f.read()
    try:
        assert '"intent": "CASUAL"' in logs
        assert '"situation": ""' in logs
        assert '"hints": ""' in logs
    except AssertionError:
        print("Triage log search failed. Logs tail:")
        print(logs)
        raise
    print("✓ Casual triage successful (Schema validated in logs).")

if __name__ == "__main__":
    import subprocess
    test_triage_casual()
