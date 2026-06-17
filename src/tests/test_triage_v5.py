import requests
import json
import time

def test_triage_casual():
    print("Testing CASUAL vibe triage...")
    # Simulate a casual query to the attendant
    payload = {"query": "Hello there!", "source": "TEST_CLIENT"}
    # This assumes the Foyer/Router has a triage endpoint or we hit the waterfall directly
    # Using the router's stream ingest as a proxy
    resp = requests.post("http://localhost:8765/stream_ingest", json=payload)
    assert resp.status_code == 200
    print("✓ Casual triage successful (Ingest OK).")

if __name__ == "__main__":
    test_triage_casual()
