import asyncio
import websockets
import json
import requests
import time

WS_URL = "ws://localhost:8765"
STATUS_URL = "http://localhost:8765/status"

async def test_triage_casual_with_priming():
    print("Testing CASUAL vibe triage with Early Priming via WebSocket (Attendant-Aware)...")
    
    # 0. Wake the lab and poll for readiness
    requests.post("http://localhost:8765/wake")
    
    print("Waiting for Attendant/Foyer to report READY state...")
    ready = False
    for i in range(20):
        try:
            status = requests.get(STATUS_URL, timeout=2).json()
            # The manager sets state to OPERATIONAL when ready
            if status.get("state") == "OPERATIONAL":
                ready = True
                break
            print(f"Status: {status.get('state')}")
        except Exception as e:
            print(f"Polling failed: {e}")
        time.sleep(10)
        
    assert ready, "Lab failed to reach READY state in time."
    
    # 1. Listen on WebSocket first
    async with websockets.connect(WS_URL) as ws:
        # Handshake
        await ws.send(json.dumps({"type": "handshake", "version": "5.0.0-foyer"}))
        
        # 2. Trigger the query
        payload = {"content": "Hi! How do you calculate pi?", "type": "text_input", "request_id": "TEST_PRIMING_123"}
        await ws.send(json.dumps(payload))
        
        priming_received = False
        start_time = time.time()
        
        while time.time() - start_time < 60:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(msg)
                
                # Check for crosstalk channel "insight" and the expected priming message
                if data.get("type") == "crosstalk":
                    brain = data.get("brain", "")
                    print(f"DEBUG: Received crosstalk: {brain}")
                    if "Initiating mental synthesis" in brain or "Acknowledged" in brain:
                        print("✓ First Try Priming successful (WebSocket validated).")
                        priming_received = True
                        break
            except asyncio.TimeoutError:
                break
        
        assert priming_received, "Priming broadcast not received!"

if __name__ == "__main__":
    asyncio.run(test_triage_casual_with_priming())
